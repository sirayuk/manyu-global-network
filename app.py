import os
import time
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai
from google.genai import types

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "manyu_global_network_secret_key")

db_url = os.environ.get("DATABASE_URL", "sqlite:///manyu.db").strip()
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

ADMIN_PASSCODE = os.environ.get("ADMIN_PASSCODE", "manyu2026")
db = SQLAlchemy(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

SYSTEM_PROMPT = """You are Gemini, the official Primary Correspondent for the Manyu Global Network (MGN).
You represent the people of Manyu Division (Mamfe Central, Eyumojock, Upper Bayang, Akwaya) across Cameroon and the global diaspora.
Welcome members warmly in English or French, share cultural knowledge about Manyu clans (Banyang, Ejagham, Anyang, Boki), villages, cocoa farming heritage, Manyu legends (such as Prof. Peter Agbor-Tabi, Dr. Tabe Tando, Emmanuel Tabi Egbe), and Kenyang/Ejagham vocabulary."""

def extract_country_key(location_text):
    if not location_text:
        return ""
    parts = [p.strip().lower() for p in location_text.replace("/", ",").split(",") if p.strip()]
    return parts[-1] if parts else location_text.strip().lower()

def is_outside_cameroon(location_text):
    country = extract_country_key(location_text)
    return bool(country) and country not in {"cameroon", "cameroun", "cm"}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    parent_full_name = db.Column(db.String(120), nullable=False, default="")
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    subdivision = db.Column(db.String(80), nullable=False)
    village = db.Column(db.String(100), nullable=False)
    quarter = db.Column(db.String(120), default="")
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
    population = db.Column(db.String(80), default="Not specified")
    area_sq_km = db.Column(db.String(80), default="Not specified")
    adjacent_before = db.Column(db.String(120), default="")
    adjacent_after = db.Column(db.String(120), default="")
    added_by_name = db.Column(db.String(120), default="Manyu Archive")
    added_by_email = db.Column(db.String(120), default="")
    overview = db.Column(db.Text, nullable=False)
    stories = db.relationship("ElderStory", backref="village", lazy=True)
    pending_updates = db.relationship("VillageUpdate", backref="village", lazy=True)

class VillageUpdate(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    village_id = db.Column(db.Integer, db.ForeignKey("village.id"), nullable=False)
    contributor_name = db.Column(db.String(120), nullable=False)
    contributor_contact = db.Column(db.String(120), nullable=False)
    proposed_population = db.Column(db.String(80), default="")
    proposed_area = db.Column(db.String(80), default="")
    proposed_between = db.Column(db.String(180), default="")
    additional_info = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), default="Pending Creator Review")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    status = db.Column(db.String(40), nullable=False)
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

class CommunityEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    event_type = db.Column(db.String(80), nullable=False)
    event_date = db.Column(db.String(80), nullable=False)
    village_or_branch = db.Column(db.String(120), nullable=False)
    location_country = db.Column(db.String(120), nullable=False)
    organizer = db.Column(db.String(120), nullable=False)
    contact = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class VillageProject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    village_name = db.Column(db.String(120), nullable=False)
    project_title = db.Column(db.String(200), nullable=False)
    currency = db.Column(db.String(20), default="FCFA")
    target_amount = db.Column(db.Integer, nullable=False)
    raised_amount = db.Column(db.Integer, default=0)
    description = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Social Wall, Likes, Comments, Follows & Community Chat Models
class SocialPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_name = db.Column(db.String(120), nullable=False)
    author_village = db.Column(db.String(120), default="Manyu Division")
    content = db.Column(db.Text, nullable=False)
    image_url = db.Column(db.String(400), default="")
    likes_count = db.Column(db.Integer, default=0)
    shares_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    comments = db.relationship("PostComment", backref="post", lazy=True, cascade="all, delete-orphan")

class PostComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("social_post.id"), nullable=False)
    commenter_name = db.Column(db.String(120), nullable=False)
    comment_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class MemberFollow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    follower_name = db.Column(db.String(120), nullable=False)
    followed_name = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_name = db.Column(db.String(120), nullable=False)
    sender_location = db.Column(db.String(120), default="")
    message_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def ensure_schema_columns():
    alter_statements = [
        "ALTER TABLE \"user\" ADD COLUMN parent_full_name VARCHAR(120) DEFAULT ''",
        "ALTER TABLE \"user\" ADD COLUMN quarter VARCHAR(120) DEFAULT ''",
        "ALTER TABLE village ADD COLUMN population VARCHAR(80) DEFAULT 'Not specified'",
        "ALTER TABLE village ADD COLUMN area_sq_km VARCHAR(80) DEFAULT 'Not specified'",
        "ALTER TABLE village ADD COLUMN adjacent_before VARCHAR(120) DEFAULT ''",
        "ALTER TABLE village ADD COLUMN adjacent_after VARCHAR(120) DEFAULT ''",
        "ALTER TABLE village ADD COLUMN added_by_name VARCHAR(120) DEFAULT 'Manyu Archive'",
        "ALTER TABLE village ADD COLUMN added_by_email VARCHAR(120) DEFAULT ''"
    ]
    for stmt in alter_statements:
        try:
            db.session.execute(text(stmt))
            db.session.commit()
        except Exception:
            db.session.rollback()

def seed_data():
    if Village.query.count() == 0:
        v1 = Village(name="Ossing", subdivision="Eyumojock", clan="Ejagham", population="~8,500", area_sq_km="145 sq km", adjacent_before="Ekondo Titi / Border Corridor", adjacent_after="Eyumojock", added_by_name="Ayuk Besong", added_by_email="sirayuk@yahoo.com", overview="Historic gateway community in Eyumojock known for rich Ejagham traditions, fertile cocoa plantations, and cross-border commerce.")
        v2 = Village(name="Besongabang", subdivision="Mamfe Central", clan="Banyang", population="~6,200", area_sq_km="88 sq km", adjacent_before="Mamfe Town", adjacent_after="Bachuo-Akagbe", added_by_name="Ayuk Besong", added_by_email="sirayuk@yahoo.com", overview="A vibrant educational and cultural hub just outside Mamfe town, home to historic institutions and proud Banyang heritage.")
        v3 = Village(name="Bachuo-Akagbe", subdivision="Upper Bayang", clan="Banyang", population="~5,400", area_sq_km="112 sq km", adjacent_before="Besongabang", adjacent_after="Kendem", added_by_name="Ayuk Besong", added_by_email="sirayuk@yahoo.com", overview="Strategically positioned along the Mamfe-Bamenda corridor, renowned for community unity, cocoa farming, and hospitality.")
        v4 = Village(name="Kendem", subdivision="Upper Bayang", clan="Banyang", population="~4,900", area_sq_km="160 sq km", adjacent_before="Bachuo-Akagbe", adjacent_after="Mbinda", added_by_name="Ayuk Besong", added_by_email="sirayuk@yahoo.com", overview="Nestled in the lush cocoa hills of Upper Bayang, celebrated for storytelling, palm wine traditions, and strong diaspora ties.")
        v5 = Village(name="Nchang", subdivision="Mamfe Central", clan="Banyang", population="~4,100", area_sq_km="74 sq km", adjacent_before="Mamfe", adjacent_after="Etoko", added_by_name="Ayuk Besong", added_by_email="sirayuk@yahoo.com", overview="Known for strong community associations, fertile cocoa and plantain farms, and deep Banyang cultural roots.")
        v6 = Village(name="Mbinda", subdivision="Akwaya", clan="Boki / Anyang", population="~3,600", area_sq_km="195 sq km", adjacent_before="Kendem", adjacent_after="Akwaya Central", added_by_name="Ayuk Besong", added_by_email="sirayuk@yahoo.com", overview="Highland and forest community in Akwaya with rich oral traditions, timber/cocoa livelihoods, and cross-clan ties.")
        db.session.add_all([v1, v2, v3, v4, v5, v6])
        db.session.commit()
        db.session.add_all([
            ElderStory(village_id=v1.id, elder_name="Chief Ndep Ojong", title="The Founding Crossings of the Cross River", story_text="Our ancestors settled along the fertile banks where trade routes met the forest. Every family compound kept the sacred Ekpe drum as a symbol of peace, justice, and brotherhood across clans."),
            ElderStory(village_id=v2.id, elder_name="Pa Tanyi Agbor", title="Why Hospitality is the First Law of Besongabang", story_text="In Manyu, no traveler passes a compound hungry. Our forefathers taught that a stranger welcomed with kola nut and palm wine becomes a brother for life.")
        ])

    if ManyuLegend.query.count() == 0:
        db.session.add_all([
            ManyuLegend(full_name="Prof. Peter Agbor-Tabi", status="In Loving Memory (Late)", subdivision_village="Eyumojock (Ejagham)", title_role="Former Minister of Higher Education, Chancellor of Yaounde II & Assistant Secretary General at the Presidency", photo_url="", tribute="A towering statesman, scholar, and unifying pillar of Manyu Division who championed higher education and Manyu representation at the highest levels."),
            ManyuLegend(full_name="Dr. Tabe Tando", status="Living Legend", subdivision_village="Manyu Division", title_role="Renowned Statesman, Diplomat & Community Leader", photo_url="", tribute="Celebrated across Manyu and the global diaspora for visionary leadership, mentorship, and steadfast dedication to Manyang unity and progress."),
            ManyuLegend(full_name="Hon. Emmanuel Tabi Egbe", status="In Loving Memory (Late)", subdivision_village="Upper Bayang (Banyang)", title_role="Founding Statesman, Legal Luminary & Cabinet Minister", photo_url="", tribute="One of the founding architects of modern Cameroon and a proud son of Upper Bayang who paved the way for generations of Manyu leaders."),
            ManyuLegend(full_name="Chief Ako Defang Mengot", status="In Loving Memory (Late)", subdivision_village="Upper Bayang", title_role="Pioneer Educator & Traditional Leader", photo_url="", tribute="Director of Education in former West Cameroon whose lifelong commitment to schools transformed literacy across Manyu."),
            ManyuLegend(full_name="Prof. Ayuk Takem", status="Living Legend", subdivision_village="Manyu Division", title_role="Distinguished Academic, Researcher & Former Minister", photo_url="", tribute="Respected scientist and educator inspiring Manyang scholars at home and in international universities."),
            ManyuLegend(full_name="Engr. Jerome Etah", status="In Loving Memory (Late)", subdivision_village="Eyumojock (Ejagham)", title_role="Veteran Engineer & Former Minister of Public Works", photo_url="", tribute="Remembered for infrastructure advocacy and dedicated public service to Manyu Division and the nation.")
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

    if CommunityEvent.query.count() == 0:
        db.session.add_all([
            CommunityEvent(title="Manyu Global Annual Cultural & Cocoa Summit", event_type="Cultural Festival & Summit", event_date="December 28, 2026", village_or_branch="Mamfe Central & Global Branches", location_country="Mamfe, Cameroon", organizer="Manyu Global Network Committee", contact="sirayuk@yahoo.com", details="Gathering of Manyang from Mamfe, Eyumojock, Upper Bayang, Akwaya, and the diaspora to celebrate Ekpe/Nkim heritage and cocoa agribusiness."),
            CommunityEvent(title="USA & Canada Manyu Diaspora Family Meetup", event_type="Diaspora Country Meetup", event_date="January 16, 2027", village_or_branch="All Manyu Villages", location_country="Houston, USA", organizer="Diaspora Coordination Desk", contact="+237 681 935 677", details="Connecting villagers from Ossing, Besongabang, Bachuo-Akagbe, and Kendem living across North America.")
        ])

    if VillageProject.query.count() == 0:
        db.session.add_all([
            VillageProject(village_name="Besongabang & Mamfe Central", project_title="Clean Community Water Borehole & Solar Pump", currency="FCFA", target_amount=2500000, raised_amount=950000, description="Providing reliable clean drinking water for village quarters and schools."),
            VillageProject(village_name="Ossing & Eyumojock", project_title="Improved Cocoa Seedling Nursery & Farmer Cooperative", currency="FCFA", target_amount=1800000, raised_amount=720000, description="Distributing high-yield cocoa seedlings and fermentation boxes to local families."),
            VillageProject(village_name="All Manyu Subdivisions", project_title="Manyu Youth STEM & Secondary School Scholarship Fund", currency="FCFA", target_amount=3000000, raised_amount=1150000, description="Supporting bright students across Mamfe, Eyumojock, Upper Bayang, and Akwaya.")
        ])

    if SocialPost.query.count() == 0:
        p1 = SocialPost(author_name="Ayuk Besong", author_village="Manyu Global Coordinator • Cameroon", content="Nkuba & welcome to the Manyu Social Wall! Share what is on your mind, reconnect with your village and quarter, follow fellow Manyang, and jump into our live community chat.", likes_count=14, shares_count=5)
        p2 = SocialPost(author_name="Mama Enow Grace", author_village="Mamfe Central", content="Cocoa harvest season in Manyu is looking strong this year! Proud of our farmers keeping our families and heritage thriving.", likes_count=9, shares_count=3)
        db.session.add_all([p1, p2])
        db.session.commit()
        db.session.add(PostComment(post_id=p1.id, commenter_name="Dr. Tabi Ashu", comment_text="Great initiative! Having our own Manyu wall and chat brings home and diaspora closer together."))

    if ChatMessage.query.count() == 0:
        db.session.add_all([
            ChatMessage(sender_name="Ayuk Besong", sender_location="Cameroon", message_text="Welcome to the Manyu Live Community Chat! Say hello and drop your village name."),
            ChatMessage(sender_name="Enow Walters", sender_location="Houston, USA", message_text="Greetings from Texas! Proud son of Upper Bayang checking in.")
        ])

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

@app.route("/feed", methods=["GET", "POST"])
def feed():
    current_name = session.get("user_name", "")
    if request.method == "POST":
        action = request.form.get("action", "create_post")
        if action == "create_post":
            author = request.form.get("author_name", "").strip() or current_name or "Manyu Member"
            village_tag = request.form.get("author_village", "").strip() or "Manyu Division"
            content = request.form.get("content", "").strip()
            image_url = request.form.get("image_url", "").strip()
            if content:
                db.session.add(SocialPost(author_name=author, author_village=village_tag, content=content, image_url=image_url))
                db.session.commit()
                flash("Your post is now live on the Manyu Social Wall!")
        elif action == "like_post":
            post = SocialPost.query.get(request.form.get("post_id"))
            if post:
                post.likes_count += 1
                db.session.commit()
        elif action == "share_post":
            post = SocialPost.query.get(request.form.get("post_id"))
            if post:
                post.shares_count += 1
                sharer = current_name or "A Manyang Member"
                db.session.add(SocialPost(
                    author_name=sharer,
                    author_village="Shared Post",
                    content=f"Shared from {post.author_name}: \"{post.content}\"",
                    image_url=post.image_url
                ))
                db.session.commit()
                flash(f"Shared {post.author_name}'s post to the wall!")
        elif action == "comment_post":
            post_id = request.form.get("post_id")
            commenter = request.form.get("commenter_name", "").strip() or current_name or "Manyu Member"
            comment_text = request.form.get("comment_text", "").strip()
            if post_id and comment_text:
                db.session.add(PostComment(post_id=post_id, commenter_name=commenter, comment_text=comment_text))
                db.session.commit()
        elif action == "follow_member":
            follower = request.form.get("follower_name", "").strip() or current_name or "Guest Member"
            followed = request.form.get("followed_name", "").strip()
            if followed and follower.lower() != followed.lower():
                existing = MemberFollow.query.filter(
                    db.func.lower(MemberFollow.follower_name) == follower.lower(),
                    db.func.lower(MemberFollow.followed_name) == followed.lower()
                ).first()
                if existing:
                    db.session.delete(existing)
                    db.session.commit()
                    flash(f"Unfollowed {followed}.")
                else:
                    db.session.add(MemberFollow(follower_name=follower, followed_name=followed))
                    db.session.commit()
                    flash(f"You are now following {followed}!")
        elif action == "send_chat":
            sender = request.form.get("sender_name", "").strip() or current_name or "Manyu Member"
            location = request.form.get("sender_location", "").strip()
            msg = request.form.get("message_text", "").strip()
            if msg:
                db.session.add(ChatMessage(sender_name=sender, sender_location=location, message_text=msg))
                db.session.commit()
        return redirect(url_for("feed"))

    feed_filter = request.args.get("filter", "all")
    followed_names = []
    if current_name:
        followed_names = [
            f.followed_name for f in MemberFollow.query.filter(
                db.func.lower(MemberFollow.follower_name) == current_name.lower()
            ).all()
        ]

    if feed_filter == "following" and followed_names:
        posts = SocialPost.query.filter(SocialPost.author_name.in_(followed_names)).order_by(SocialPost.created_at.desc()).all()
    else:
        posts = SocialPost.query.order_by(SocialPost.created_at.desc()).all()

    chat_messages = ChatMessage.query.order_by(ChatMessage.created_at.desc()).limit(30).all()[::-1]
    return render_template("feed.html", posts=posts, chat_messages=chat_messages, followed_names=followed_names, feed_filter=feed_filter)

@app.route("/api/chat-messages")
def api_chat_messages():
    msgs = ChatMessage.query.order_by(ChatMessage.created_at.desc()).limit(30).all()[::-1]
    return jsonify([
        {
            "sender_name": m.sender_name,
            "sender_location": m.sender_location,
            "message_text": m.message_text,
            "time": m.created_at.strftime("%H:%M")
        } for m in msgs
    ])

@app.route("/directory")
def directory():
    q_sub = request.args.get("subdivision", "").strip()
    q_village = request.args.get("village", "").strip()
    q_quarter = request.args.get("quarter", "").strip()
    q_country = request.args.get("country", "").strip()
    q_skill = request.args.get("skill", "").strip()

    query = User.query
    if q_sub:
        query = query.filter(User.subdivision == q_sub)
    if q_village:
        query = query.filter(User.village.ilike(f"%{q_village}%"))
    if q_quarter:
        query = query.filter(User.quarter.ilike(f"%{q_quarter}%"))
    if q_country:
        query = query.filter(User.current_location.ilike(f"%{q_country}%"))
    if q_skill:
        query = query.filter(User.profession_skills.ilike(f"%{q_skill}%"))

    members = query.order_by(User.created_at.desc()).all()
    return render_template("directory.html", members=members, q_sub=q_sub, q_village=q_village, q_quarter=q_quarter, q_country=q_country, q_skill=q_skill)

@app.route("/events", methods=["GET", "POST"])
def events():
    if request.method == "POST":
        db.session.add(CommunityEvent(
            title=request.form["title"].strip(),
            event_type=request.form["event_type"],
            event_date=request.form["event_date"].strip(),
            village_or_branch=request.form["village_or_branch"].strip(),
            location_country=request.form["location_country"].strip(),
            organizer=request.form["organizer"].strip(),
            contact=request.form["contact"].strip(),
            details=request.form["details"].strip()
        ))
        db.session.commit()
        flash("Event / Notice published to the Manyu Community Board!")
        return redirect(url_for("events"))
    type_filter = request.args.get("event_type", "").strip()
    all_events = CommunityEvent.query.filter_by(event_type=type_filter).order_by(CommunityEvent.created_at.desc()).all() if type_filter else CommunityEvent.query.order_by(CommunityEvent.created_at.desc()).all()
    return render_template("events.html", events=all_events, selected_type=type_filter)

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
        email = request.form["email"].strip().lower()
        if User.query.filter_by(email=email).first():
            flash("An account with this email already exists.")
            return redirect(url_for("signup"))

        full_name = request.form["full_name"].strip()
        parent_full_name = request.form.get("parent_full_name", "").strip()
        village = request.form["village"].strip()
        quarter = request.form.get("quarter", "").strip()
        current_location = request.form["current_location"].strip()

        new_user = User(
            full_name=full_name,
            parent_full_name=parent_full_name,
            email=email,
            password_hash=generate_password_hash(request.form["password"]),
            subdivision=request.form["subdivision"],
            village=village,
            quarter=quarter,
            current_location=current_location,
            profession_skills=request.form["profession_skills"].strip(),
            bio=request.form["bio"].strip(),
            is_elder=("is_elder" in request.form)
        )
        db.session.add(new_user)
        db.session.commit()

        if parent_full_name:
            db.session.add(FamilyNode(
                owner_id=new_user.id,
                person_name=parent_full_name,
                relation="Parent (Father / Mother)",
                parent_name="Ancestral Line",
                birth_year="",
                ancestral_village=f"{village} ({quarter})" if quarter else village
            ))
            db.session.add(FamilyNode(
                owner_id=new_user.id,
                person_name=full_name,
                relation="Self (Registered Member)",
                parent_name=f"Child of {parent_full_name}",
                birth_year="",
                ancestral_village=f"{village} ({quarter})" if quarter else village
            ))

            matching_relatives = User.query.filter(
                User.id != new_user.id,
                db.func.lower(User.parent_full_name) == parent_full_name.lower()
            ).all()
            for rel in matching_relatives:
                db.session.add(FamilyNode(
                    owner_id=rel.id,
                    person_name=full_name,
                    relation=f"Sibling / Family Connection (Same Parent: {parent_full_name})",
                    parent_name=f"Child of {parent_full_name}",
                    birth_year="",
                    ancestral_village=f"{village} ({quarter})" if quarter else village
                ))
                db.session.add(FamilyNode(
                    owner_id=new_user.id,
                    person_name=rel.full_name,
                    relation=f"Sibling / Family Connection (Same Parent: {parent_full_name})",
                    parent_name=f"Child of {parent_full_name}",
                    birth_year="",
                    ancestral_village=f"{rel.village} ({rel.quarter})" if rel.quarter else rel.village
                ))

        country_key = extract_country_key(current_location)
        if is_outside_cameroon(current_location):
            same_village_diaspora = [
                u for u in User.query.filter(
                    User.id != new_user.id,
                    db.func.lower(User.village) == village.lower()
                ).all()
                if extract_country_key(u.current_location) == country_key
            ]
            for mate in same_village_diaspora:
                db.session.add(FamilyNode(
                    owner_id=new_user.id,
                    person_name=mate.full_name,
                    relation=f"Same Village in {country_key.title()} ({village})",
                    parent_name=mate.profession_skills,
                    birth_year="",
                    ancestral_village=f"{village} ({mate.quarter})" if mate.quarter else village
                ))
                db.session.add(FamilyNode(
                    owner_id=mate.id,
                    person_name=full_name,
                    relation=f"Same Village in {country_key.title()} ({village})",
                    parent_name=new_user.profession_skills,
                    birth_year="",
                    ancestral_village=f"{village} ({quarter})" if quarter else village
                ))

        db.session.commit()
        session["user_id"] = new_user.id
        session["user_name"] = new_user.full_name
        session["user_email"] = new_user.email
        flash(f"Welcome to Manyu Global Network! Profile created for {village}.")
        return redirect(url_for("family_tree"))
    return render_template("signup.html")

@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"].strip().lower()
    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, request.form["password"]):
        session["user_id"] = user.id
        session["user_name"] = user.full_name
        session["user_email"] = user.email
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
            v_name = request.form["name"].strip()
            existing = Village.query.filter(db.func.lower(Village.name) == v_name.lower()).first()
            if existing:
                flash(f"'{existing.name}' is already in the archive (added by {existing.added_by_name}). Use 'Propose Additional Info for Village' so {existing.added_by_name} can review and confirm it.")
                return redirect(url_for("villages"))

            creator_name = request.form.get("creator_name", "").strip() or session.get("user_name", "") or "Community Member"
            creator_email = request.form.get("creator_email", "").strip().lower() or session.get("user_email", "")
            db.session.add(Village(
                name=v_name,
                subdivision=request.form["subdivision"],
                clan=request.form["clan"].strip(),
                population=request.form.get("population", "").strip() or "Not specified",
                area_sq_km=request.form.get("area_sq_km", "").strip() or "Not specified",
                adjacent_before=request.form.get("adjacent_before", "").strip(),
                adjacent_after=request.form.get("adjacent_after", "").strip(),
                added_by_name=creator_name,
                added_by_email=creator_email,
                overview=request.form["overview"].strip()
            ))
            db.session.commit()
            flash(f"Village '{v_name}' added! You ({creator_name}) are recorded as its confirmer for future additions.")

        elif form_type == "propose_update":
            v_id = request.form.get("village_id")
            village_obj = Village.query.get(v_id)
            if village_obj:
                db.session.add(VillageUpdate(
                    village_id=village_obj.id,
                    contributor_name=request.form["contributor_name"].strip(),
                    contributor_contact=request.form["contributor_contact"].strip(),
                    proposed_population=request.form.get("proposed_population", "").strip(),
                    proposed_area=request.form.get("proposed_area", "").strip(),
                    proposed_between=request.form.get("proposed_between", "").strip(),
                    additional_info=request.form["additional_info"].strip(),
                    status="Pending Creator Review"
                ))
                db.session.commit()
                flash(f"Additional info submitted for {village_obj.name}. Waiting for {village_obj.added_by_name} (who added the village) to confirm and review.")

        elif form_type == "review_update":
            upd = VillageUpdate.query.get(request.form.get("update_id"))
            decision = request.form.get("decision")
            confirmer_email = request.form.get("confirmer_email", "").strip().lower()
            confirmer_pass = request.form.get("confirmer_passcode", "").strip()
            if upd:
                village_obj = Village.query.get(upd.village_id)
                owner_email = (village_obj.added_by_email or "").strip().lower()
                is_authorized = (confirmer_pass == ADMIN_PASSCODE) or (owner_email and confirmer_email == owner_email)
                if not is_authorized:
                    flash(f"Only {village_obj.added_by_name} (who added {village_obj.name}) or the site Admin can confirm/review additional information for this village.")
                    return redirect(url_for("villages"))

                if decision == "approve":
                    if upd.proposed_population:
                        village_obj.population = upd.proposed_population
                    if upd.proposed_area:
                        village_obj.area_sq_km = upd.proposed_area
                    if upd.proposed_between:
                        village_obj.overview += f" | Location Note: {upd.proposed_between}"
                    village_obj.overview += f" | Confirmed Addition ({upd.contributor_name}): {upd.additional_info}"
                    upd.status = f"Confirmed by {village_obj.added_by_name}"
                    db.session.commit()
                    flash(f"Additional information for {village_obj.name} confirmed and published!")
                elif decision == "reject":
                    upd.status = f"Declined by {village_obj.added_by_name}"
                    db.session.commit()
                    flash("Submission marked as declined by village creator.")

        elif form_type == "add_story":
            db.session.add(ElderStory(
                village_id=request.form["village_id"],
                elder_name=request.form["elder_name"].strip(),
                title=request.form["title"].strip(),
                story_text=request.form["story_text"].strip(),
                media_url=request.form.get("media_url", "").strip()
            ))
            db.session.commit()
            flash("Elder's story preserved in the archive!")

        return redirect(url_for("villages"))

    sub_filter = request.args.get("subdivision", "")
    all_villages = Village.query.filter_by(subdivision=sub_filter).all() if sub_filter else Village.query.all()
    pending_updates = VillageUpdate.query.filter_by(status="Pending Creator Review").order_by(VillageUpdate.created_at.desc()).all()
    return render_template("villages.html", villages=all_villages, selected_sub=sub_filter, pending_updates=pending_updates)

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
    data = request.get_json() or {}
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"reply": "Please enter a question for Gemini, your Manyu Global Network Correspondent."})
    if not gemini_client:
        return jsonify({"reply": "Gemini Correspondent is ready! Add your GEMINI_API_KEY in Render's Environment Variables to activate live AI responses."})

    attempts = [
        ("gemini-2.5-flash", 1.5),
        ("gemini-2.5-flash", 3.0),
        ("gemini-2.5-flash-lite", 0.0),
    ]
    last_error = ""
    for model_name, backoff_sec in attempts:
        try:
            response = gemini_client.models.generate_content(
                model=model_name,
                contents=user_message,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT, temperature=0.6)
            )
            return jsonify({"reply": response.text})
        except Exception as e:
            last_error = str(e)
            is_transient = "503" in last_error or "UNAVAILABLE" in last_error or "429" in last_error or "RESOURCE_EXHAUSTED" in last_error
            if not is_transient:
                break
            if backoff_sec > 0:
                time.sleep(backoff_sec)

    return jsonify({"reply": "Gemini is busy right now due to high traffic. Please wait 15 seconds and send your message again."})

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

@app.route("/donate", methods=["GET", "POST"])
def donate():
    if request.method == "POST":
        action = request.form.get("action", "")
        passcode = request.form.get("admin_passcode", "").strip()
        if passcode != ADMIN_PASSCODE:
            flash("Incorrect Admin Passcode. Only Admin Ayuk Besong can add or update project totals.")
            return redirect(url_for("donate"))

        if action == "add_project":
            db.session.add(VillageProject(
                village_name=request.form["village_name"].strip(),
                project_title=request.form["project_title"].strip(),
                currency=request.form.get("currency", "FCFA"),
                target_amount=int(request.form["target_amount"]),
                raised_amount=int(request.form.get("raised_amount") or 0),
                description=request.form["description"].strip()
            ))
            db.session.commit()
            flash("New village development project added!")
        elif action == "update_progress":
            proj = VillageProject.query.get(request.form.get("project_id"))
            if proj:
                proj.raised_amount += int(request.form.get("added_amount") or 0)
                db.session.commit()
                flash(f"Updated confirmed funding for '{proj.project_title}'.")
        return redirect(url_for("donate"))

    projects = VillageProject.query.order_by(VillageProject.created_at.desc()).all()
    is_postgres = db_url.startswith("postgresql://")
    return render_template("donate.html", projects=projects, is_postgres=is_postgres)

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

    current_user = User.query.get(user_id)
    connected_members = []
    same_village_abroad = []
    country_filter = request.args.get("country", "").strip().lower()

    if current_user:
        if current_user.parent_full_name:
            connected_members = User.query.filter(
                User.id != current_user.id,
                db.func.lower(User.parent_full_name) == current_user.parent_full_name.lower()
            ).all()

        if is_outside_cameroon(current_user.current_location):
            my_country = extract_country_key(current_user.current_location)
            same_village_abroad = [
                u for u in User.query.filter(
                    User.id != current_user.id,
                    db.func.lower(User.village) == current_user.village.lower()
                ).all()
                if is_outside_cameroon(u.current_location) and extract_country_key(u.current_location) == my_country
            ]
        elif country_filter:
            same_village_abroad = [
                u for u in User.query.filter(
                    User.id != current_user.id,
                    db.func.lower(User.village) == current_user.village.lower()
                ).all()
                if is_outside_cameroon(u.current_location) and extract_country_key(u.current_location) == country_filter
            ]

    return render_template(
        "family_tree.html",
        nodes=FamilyNode.query.filter_by(owner_id=user_id).all(),
        current_user=current_user,
        connected_members=connected_members,
        same_village_abroad=same_village_abroad,
        country_filter=country_filter
    )

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
    ensure_schema_columns()
    seed_data()

if __name__ == "__main__":
    app.run(debug=True)
