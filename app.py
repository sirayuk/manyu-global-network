import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "manyu_global_network_secret_key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///manyu.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "manyu2026")
db = SQLAlchemy(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

SYSTEM_PROMPT = """You are Gemini, the official Primary Correspondent for the Manyu Global Network (MGN).
You represent the people of Manyu Division (Mamfe Central, Eyumojock, Upper Bayang, Akwaya) across Cameroon and the global diaspora.
Welcome members warmly in English or French, share cultural knowledge about Manyu clans (Banyang, Ejagham, Anyang, Boki), villages, cocoa farming heritage, Manyu legends (such as Prof. Peter Agbor-Tabi, Dr. Tabe Tando, Emmanuel Tabi Egbe), and Kenyang/Ejagham vocabulary."""

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    subdivision = db.Column(db.String(80), nullable=False)
    village = db.Column(db.String(100), nullable=False)
    current_location = db.Column(db.String(120), nullable=False)
    profession_skills = db.Column(db.String(200), nullable=False)
    bio = db.Column(db.Text)
    is_elder = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Village(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    subdivision = db.Column(db.String(80), nullable=False)
    clan = db.Column(db.String(100))
    overview = db.Column(db.Text, nullable=False)
    stories = db.relationship("ElderStory", backref="village", lazy=True)

class ElderStory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    village_id = db.Column(db.Integer, db.ForeignKey("village.id"), nullable=False)
    elder_name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    story_text = db.Column(db.Text, nullable=False)
    media_url = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ManyuLegend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(150), nullable=False)
    status = db.Column(db.String(40), nullable=False)  # Living Legend or In Loving Memory (Late)
    subdivision_village = db.Column(db.String(120), nullable=False)
    title_role = db.Column(db.String(180), nullable=False)
    photo_url = db.Column(db.String(400))
    tribute = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class LexiconEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    language = db.Column(db.String(60), nullable=False)
    word_or_phrase = db.Column(db.String(150), nullable=False)
    english_meaning = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    usage_note = db.Column(db.String(250))
    contributed_by = db.Column(db.String(100), default="Manyu Linguistic Archive")

class HelpTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_name = db.Column(db.String(120), nullable=False)
    sender_contact = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="Open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FamilyNode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    person_name = db.Column(db.String(120), nullable=False)
    relation = db.Column(db.String(80), nullable=False)
    parent_name = db.Column(db.String(120))
    birth_year = db.Column(db.String(20))
    ancestral_village = db.Column(db.String(100))

class MarketItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_name = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=False)
    price = db.Column(db.String(60), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    contact = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class TalkPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_name = db.Column(db.String(120), nullable=False)
    topic = db.Column(db.String(100), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def seed_data():
    if Village.query.count() == 0:
        v1 = Village(name="Ossing", subdivision="Eyumojock", clan="Ejagham", overview="Historic gateway community in Eyumojock known for rich Ejagham traditions, fertile cocoa plantations, and cross-border commerce.")
        v2 = Village(name="Besongabang", subdivision="Mamfe Central", clan="Banyang", overview="A vibrant educational and cultural hub just outside Mamfe town, home to historic institutions and proud Banyang heritage.")
        v3 = Village(name="Bachuo-Akagbe", subdivision="Upper Bayang", clan="Banyang", overview="Strategically positioned along the Mamfe-Bamenda corridor, renowned for community unity, cocoa farming, and hospitality.")
        v4 = Village(name="Kendem", subdivision="Upper Bayang", clan="Banyang", overview="Nestled in the lush cocoa hills of Upper Bayang, celebrated for storytelling, palm wine traditions, and strong diaspora ties.")
        db.session.add_all([v1, v2, v3, v4])
        db.session.commit()
        db.session.add_all([
            ElderStory(village_id=v1.id, elder_name="Chief Ndep Ojong", title="The Founding Crossings of the Cross River", story_text="Our ancestors settled along the fertile banks where trade routes met the forest. Every family compound kept the sacred Ekpe drum as a symbol of peace, justice, and brotherhood across clans."),
            ElderStory(village_id=v2.id, elder_name="Pa Tanyi Agbor", title="Why Hospitality is the First Law of Besongabang", story_text="In Manyu, no traveler passes a compound hungry. Our forefathers taught that a stranger welcomed with kola nut and palm wine becomes a brother for life.")
        ])

    if ManyuLegend.query.count() == 0:
        db.session.add_all([
            ManyuLegend(
                full_name="Prof. Peter Agbor-Tabi",
                status="In Loving Memory (Late)",
                subdivision_village="Eyumojock (Ejagham)",
                title_role="Former Minister of Higher Education, Chancellor of Yaounde II & Assistant Secretary General at the Presidency",
                photo_url="",
                tribute="A towering statesman, scholar, and unifying pillar of Manyu Division who championed higher education and Manyu representation at the highest levels."
            ),
            ManyuLegend(
                full_name="Dr. Tabe Tando",
                status="Living Legend",
                subdivision_village="Manyu Division",
                title_role="Renowned Statesman, Diplomat & Community Leader",
                photo_url="",
                tribute="Celebrated across Manyu and the global diaspora for visionary leadership, mentorship, and steadfast dedication to Manyang unity and progress."
            ),
            ManyuLegend(
                full_name="Hon. Emmanuel Tabi Egbe",
                status="In Loving Memory (Late)",
                subdivision_village="Upper Bayang (Banyang)",
                title_role="Founding Statesman, Legal Luminary & Cabinet Minister",
                photo_url="",
                tribute="One of the founding architects of modern Cameroon and a proud son of Upper Bayang who paved the way for generations of Manyu leaders."
            ),
            ManyuLegend(
                full_name="Chief Ako Defang Mengot",
                status="In Loving Memory (Late)",
                subdivision_village="Upper Bayang",
                title_role="Pioneer Educator & Traditional Leader",
                photo_url="",
                tribute="Director of Education in former West Cameroon whose lifelong commitment to schools transformed literacy across Manyu."
            ),
            ManyuLegend(
                full_name="Prof. Ayuk Takem",
                status="Living Legend",
                subdivision_village="Manyu Division",
                title_role="Distinguished Academic, Researcher & Former Minister",
                photo_url="",
                tribute="Respected scientist and educator inspiring Manyang scholars at home and in international universities."
            ),
            ManyuLegend(
                full_name="Engr. Jerome Etah",
                status="In Loving Memory (Late)",
                subdivision_village="Eyumojock (Ejagham)",
                title_role="Veteran Engineer & Former Minister of Public Works",
                photo_url="",
                tribute="Remembered for infrastructure advocacy and dedicated public service to Manyu Division and the nation."
            )
        ])

    if LexiconEntry.query.count() == 0:
        db.session.add_all([
            LexiconEntry(language="Kenyang (Banyang)", word_or_phrase="Acha mfo", english_meaning="Chief's palace / royal house", category="Culture & Royalty", usage_note="Traditional seat of leadership in a Banyang village."),
            LexiconEntry(language="Kenyang (Banyang)", word_or_phrase="Afok", english_meaning="Blessing / glory", category="Culture & Royalty", usage_note="Spoken during libations and elders' blessings."),
            LexiconEntry(language="Kenyang (Banyang)", word_or_phrase="Akap nti", english_meaning="Peace offering / gift of reconciliation", category="Culture & Royalty", usage_note="Used in traditional dispute resolution."),
            LexiconEntry(language="Kenyang (Banyang)", word_or_phrase="Bachi-mbii", english_meaning="Ancestors", category="Culture & Royalty", usage_note="Honored in oral histories and lineage trees."),
            LexiconEntry(language="Ejagham", word_or_phrase="Nkuba", english_meaning="General greeting / Hello", category="Greeting", usage_note="Standard warm greeting among Ejagham speakers."),
            LexiconEntry(language="Ejagham", word_or_phrase="U weki oo", english_meaning="Good morning", category="Greeting", usage_note="Reply: 'Iya, u weki yee'."),
            LexiconEntry(language="Ejagham", word_or_phrase="Obhasi", english_meaning="God / Supreme Creator", category="Culture & Royalty", usage_note="Used in prayers and blessings across Ejagham communities.")
        ])

    if MarketItem.query.count() == 0:
        db.session.add_all([
            MarketItem(seller_name="Mama Enow Grace", title="Grade-A Manyu Cocoa Beans, Red Palm Oil & Ndjansang", category="Agro-Produce", price="15,000 FCFA / 20L", location="Mamfe / Douala / Edea", contact="+237 681 935 677", description="Freshly harvested from Manyu cocoa and palm plantations, organic and ready for local or diaspora shipping."),
            MarketItem(seller_name="Arrey Tech Solutions", title="Custom Web & Mobile App Development", category="Professional Services", price="Starting 150,000 FCFA", location="Remote / Worldwide", contact="sirayuk@yahoo.com", description="Full-stack software engineering, e-commerce setup, and IT consulting for Manyu-owned businesses.")
        ])

    if TalkPost.query.count() == 0:
        db.session.add(TalkPost(author_name="Dr. Tabi Ashu", topic="Mentorship & Career", title="Modernizing Manyu Cocoa Plantations & Youth Tech Apprenticeships", content="Let us combine our rich cocoa and agricultural heritage with modern agribusiness and tech mentorship for Manyu youth at home and abroad."))

    if HelpTicket.query.count() == 0:
        db.session.add(HelpTicket(sender_name="Enow Walters", sender_contact="enow.walters@example.com", category="Village Record", subject="Adding Nfuni Village Elders' Archive", message="Hello Admin Ayuk Besong, our elders in Nfuni have recorded our migration history and would like it added to the Upper Bayang section.", status="Open"))

    db.session.commit()

@app.route("/")
def index():
    users = User.query.order_by(User.created_at.desc()).limit(6).all()
    villages = Village.query.limit(4).all()
    legends = ManyuLegend.query.limit(4).all()
    lexicon_preview = LexiconEntry.query.limit(4).all()
    stats = {"members": User.query.count() + 142, "villages": Village.query.count(), "legends": ManyuLegend.query.count(), "words": LexiconEntry.query.count()}
    return render_template("index.html", users=users, villages=villages, legends=legends, lexicon_preview=lexicon_preview, stats=stats)

@app.route("/legends", methods=["GET", "POST"])
def legends():
    if request.method == "POST":
        db.session.add(ManyuLegend(
            full_name=request.form["full_name"],
            status=request.form["status"],
            subdivision_village=request.form["subdivision_village"],
            title_role=request.form["title_role"],
            photo_url=request.form.get("photo_url", "").strip(),
            tribute=request.form["tribute"]
        ))
        db.session.commit()
        flash("Manyu Legend added to the Hall of Honor!")
        return redirect(url_for("legends"))
    status_filter = request.args.get("status", "")
    all_legends = ManyuLegend.query.filter_by(status=status_filter).all() if status_filter else ManyuLegend.query.all()
    return render_template("legends.html", legends=all_legends, selected_status=status_filter)

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        if User.query.filter_by(email=request.form["email"]).first():
            flash("An account with this email already exists.")
            return redirect(url_for("signup"))
        new_user = User(full_name=request.form["full_name"], email=request.form["email"], password_hash=generate_password_hash(request.form["password"]), subdivision=request.form["subdivision"], village=request.form["village"], current_location=request.form["current_location"], profession_skills=request.form["profession_skills"], bio=request.form["bio"], is_elder=("is_elder" in request.form))
        db.session.add(new_user)
        db.session.commit()
        session["user_id"] = new_user.id
        session["user_name"] = new_user.full_name
        flash("Welcome to Manyu Global Network!")
        return redirect(url_for("index"))
    return render_template("signup.html")

@app.route("/login", methods=["POST"])
def login():
    user = User.query.filter_by(email=request.form["email"]).first()
    if user and check_password_hash(user.password_hash, request.form["password"]):
        session["user_id"] = user.id
        session["user_name"] = user.full_name
        flash(f"Welcome back, {user.full_name}!")
    else:
        flash("Invalid email or password.")
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/villages", methods=["GET", "POST"])
def villages():
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "add_village":
            db.session.add(Village(name=request.form["name"], subdivision=request.form["subdivision"], clan=request.form["clan"], overview=request.form["overview"]))
            db.session.commit()
            flash("New village added to the Manyu archive!")
        elif form_type == "add_story":
            db.session.add(ElderStory(village_id=request.form["village_id"], elder_name=request.form["elder_name"], title=request.form["title"], story_text=request.form["story_text"], media_url=request.form.get("media_url", "")))
            db.session.commit()
            flash("Elder's story preserved in the archive!")
        return redirect(url_for("villages"))
    sub_filter = request.args.get("subdivision", "")
    all_villages = Village.query.filter_by(subdivision=sub_filter).all() if sub_filter else Village.query.all()
    return render_template("villages.html", villages=all_villages, selected_sub=sub_filter)

@app.route("/lexicon", methods=["GET", "POST"])
def lexicon():
    if request.method == "POST":
        db.session.add(LexiconEntry(language=request.form["language"], word_or_phrase=request.form["word_or_phrase"], english_meaning=request.form["english_meaning"], category=request.form["category"], usage_note=request.form["usage_note"], contributed_by=request.form.get("contributed_by") or "Community Member"))
        db.session.commit()
        flash("Word added to the Manyu Languages Lexicon!")
        return redirect(url_for("lexicon"))
    lang_filter = request.args.get("language", "")
    entries = LexiconEntry.query.filter_by(language=lang_filter).all() if lang_filter else LexiconEntry.query.all()
    return render_template("lexicon.html", entries=entries, selected_lang=lang_filter)

@app.route("/correspondent")
def correspondent():
    return render_template("correspondent.html")

@app.route("/api/correspondent", methods=["POST"])
def api_correspondent():
    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"reply": "Please enter a question for Gemini, your Manyu Global Network Correspondent."})
    if not gemini_client:
        return jsonify({"reply": "Gemini Correspondent is ready! Add your GEMINI_API_KEY in Render's Environment Variables to activate live AI responses."})
    try:
        response = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=user_message, config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.6))
        return jsonify({"reply": response.text})
    except Exception as e:
        return jsonify({"reply": f"Correspondent temporarily unavailable: {str(e)}"})

@app.route("/support", methods=["GET", "POST"])
def support():
    if request.method == "POST":
        action = request.form.get("action", "create")
        if action == "create":
            db.session.add(HelpTicket(sender_name=request.form["sender_name"], sender_contact=request.form["sender_contact"], category=request.form["category"], subject=request.form["subject"], message=request.form["message"]))
            db.session.commit()
            flash("Your help ticket has been saved!")
        elif action == "resolve":
            entered_pass = request.form.get("admin_passcode", "")
            if entered_pass == ADMIN_PASSCODE:
                ticket = HelpTicket.query.get(request.form.get("ticket_id"))
                if ticket:
                    ticket.status = "Resolved"
                    db.session.commit()
                    flash(f"Ticket #{ticket.id} marked as Resolved.")
            else:
                flash("Incorrect Admin Passcode. Only Admin Ayuk Besong can resolve tickets.")
        return redirect(url_for("support"))
    tickets = HelpTicket.query.order_by(HelpTicket.created_at.desc()).all()
    return render_template("support.html", tickets=tickets)

@app.route("/donate")
def donate():
    return render_template("donate.html")

@app.route("/marketplace", methods=["GET", "POST"])
def marketplace():
    if request.method == "POST":
        db.session.add(MarketItem(seller_name=request.form["seller_name"], title=request.form["title"], category=request.form["category"], price=request.form["price"], location=request.form["location"], contact=request.form["contact"], description=request.form["description"]))
        db.session.commit()
        flash("Listing published to the Manyang Marketplace!")
        return redirect(url_for("marketplace"))
    return render_template("marketplace.html", items=MarketItem.query.order_by(MarketItem.created_at.desc()).all(), talent=User.query.order_by(User.created_at.desc()).all())

@app.route("/family-tree", methods=["GET", "POST"])
def family_tree():
    user_id = session.get("user_id", 1)
    if request.method == "POST":
        db.session.add(FamilyNode(owner_id=user_id, person_name=request.form["person_name"], relation=request.form["relation"], parent_name=request.form["parent_name"], birth_year=request.form["birth_year"], ancestral_village=request.form["ancestral_village"]))
        db.session.commit()
        flash("Family member added to your lineage tree!")
        return redirect(url_for("family_tree"))
    return render_template("family_tree.html", nodes=FamilyNode.query.filter_by(owner_id=user_id).all())

@app.route("/talk-zone", methods=["GET", "POST"])
def talk_zone():
    if request.method == "POST":
        db.session.add(TalkPost(author_name=request.form["author_name"], topic=request.form["topic"], title=request.form["title"], content=request.form["content"]))
        db.session.commit()
        flash("Your topic is live in the Man-to-Man Talk Zone.")
        return redirect(url_for("talk_zone"))
    return render_template("talk_zone.html", posts=TalkPost.query.order_by(TalkPost.created_at.desc()).all())

with app.app_context():
    db.create_all()
    seed_data()

if __name__ == "__main__":
    app.run(debug=True)
