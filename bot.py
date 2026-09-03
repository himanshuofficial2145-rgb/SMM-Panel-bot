"""
SCORPIO TELEGRAM SMM BOT — SINGLE FILE
Run: python3 bot.py
The SQLite database is created automatically. Set BOT_TOKEN and SMM_API_KEY
as environment variables. ADMIN_PASSWORD defaults to himanshu.
Example: BOT_TOKEN=TOKEN SMM_API_KEY=KEY python3 bot.py
"""
import os, sys, subprocess, sqlite3, logging, asyncio
from datetime import datetime, timedelta, timezone
try:
    from dotenv import load_dotenv
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
    from telegram.constants import ChatMemberStatus
except ImportError:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'python-dotenv==1.0.1', 'python-telegram-bot[job-queue]==21.10', 'httpx==0.27.2'])
    import site, importlib
    user_site = site.getusersitepackages()
    if user_site not in sys.path:
        sys.path.append(user_site)
    importlib.invalidate_caches()
    from dotenv import load_dotenv
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
    from telegram.constants import ChatMemberStatus
from pathlib import Path
from contextlib import contextmanager
load_dotenv()
BASE_DIR=Path(__file__).resolve().parent
_configured_db=os.getenv('DATABASE_PATH','').strip()
DB_PATH=str(Path(_configured_db).expanduser() if _configured_db else BASE_DIR/'scorpio.sqlite3')
if not Path(DB_PATH).is_absolute(): DB_PATH=str(BASE_DIR/DB_PATH)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log=logging.getLogger("scorpio")
BOT_TOKEN=os.getenv("BOT_TOKEN", "8614257744:AAHOsXFwiFDtDycfyij_PNyIVjyMI1i5BEU").strip()
# DB_PATH is resolved relative to this file above, so changing the launch directory cannot create a new empty database.
SMM_API_URL=os.getenv("SMM_API_URL", "https://indiansmmhub.com/api/v2")
SMM_API_KEY=os.getenv("SMM_API_KEY", "b75dbbba40f1c2784dead6edb76f6d077d048ca5").strip()
AI_API_URL=os.getenv("AI_API_URL", "https://api.openai.com/v1")
AI_API_KEY=os.getenv("AI_API_KEY", "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").strip()
AI_MODEL=os.getenv("AI_MODEL", "gpt-4o-mini")
ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD", "himanshu")
SUPER_ADMIN_ID=8755911692

# Mandatory Telegram channels shown to users at /start and checked on VERIFY.
CODE_CHANNELS=[
    {
        "name": "@Ethical Hacker",
        "channel_id": "@Ethical_Hacker_1",
        "invite_url": "https://t.me/Ethical_Hacker_1",
    },
    {
        "name": "@Set up video",
        "channel_id": "@Set_up_video1",
        "invite_url": "https://t.me/Set_up_video1",
    },
]


SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, registered_at TEXT DEFAULT CURRENT_TIMESTAMP, balance REAL NOT NULL DEFAULT 0, referral_id INTEGER, blocked INTEGER NOT NULL DEFAULT 0, channel_verified INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS admins(user_id INTEGER PRIMARY KEY, role TEXT NOT NULL, added_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS channels(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,channel_id TEXT UNIQUE,invite_url TEXT,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS providers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,api_url TEXT,api_key TEXT,currency TEXT DEFAULT 'INR',priority INTEGER DEFAULT 1,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS services(id INTEGER PRIMARY KEY AUTOINCREMENT,provider_id INTEGER,provider_service_id TEXT,name TEXT,category TEXT,description TEXT,cost_price REAL,selling_price REAL,min_qty INTEGER,max_qty INTEGER,active INTEGER DEFAULT 1,refill_support INTEGER DEFAULT 0,cancel_support INTEGER DEFAULT 0,FOREIGN KEY(provider_id) REFERENCES providers(id));
CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,service_id INTEGER,target TEXT,quantity INTEGER,amount REAL,provider_order_id TEXT,status TEXT DEFAULT 'PENDING',created_at TEXT DEFAULT CURRENT_TIMESTAMP,refund_issued INTEGER DEFAULT 0,FOREIGN KEY(user_id) REFERENCES users(id));
CREATE TABLE IF NOT EXISTS deposits(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,amount REAL,utr TEXT UNIQUE,screenshot_file_id TEXT,status TEXT DEFAULT 'PENDING',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,kind TEXT,amount REAL,balance_after REAL,note TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS referrals(id INTEGER PRIMARY KEY AUTOINCREMENT,referrer_id INTEGER,referred_id INTEGER UNIQUE,qualified INTEGER DEFAULT 0,reward REAL DEFAULT 0);
CREATE TABLE IF NOT EXISTS redeem_codes(code TEXT PRIMARY KEY,reward REAL,usage_limit INTEGER,per_user_limit INTEGER DEFAULT 1,expires_at TEXT,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS redeem_usage(code TEXT,user_id INTEGER,used_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(code,user_id));
CREATE TABLE IF NOT EXISTS promo_codes(code TEXT PRIMARY KEY,kind TEXT,value REAL,min_order REAL DEFAULT 0,max_discount REAL,usage_limit INTEGER,expires_at TEXT,active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS promo_usage(code TEXT,user_id INTEGER,used_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(code,user_id));
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE IF NOT EXISTS support_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,message TEXT,admin_reply TEXT,status TEXT DEFAULT 'OPEN',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS bonuses(key TEXT PRIMARY KEY,value REAL DEFAULT 0,active INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS bonus_claims(key TEXT,user_id INTEGER,claimed_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(key,user_id));
CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,admin_id INTEGER,action TEXT,details TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""
def init_db():
    Path(DB_PATH).parent.mkdir(parents=True,exist_ok=True)
    with connect() as c:
        c.executescript(SCHEMA)
        user_columns={r['name'] for r in c.execute('PRAGMA table_info(users)').fetchall()}
        if 'channel_verified' not in user_columns:
            c.execute('ALTER TABLE users ADD COLUMN channel_verified INTEGER NOT NULL DEFAULT 0')
        c.execute("INSERT OR IGNORE INTO admins(user_id,role) VALUES (?,?)",(SUPER_ADMIN_ID,'SUPER_ADMIN'))
        # Preserve legacy balances that predate the transaction ledger, then reconcile
        # only against a non-empty ledger. This migration can never erase a balance.
        c.execute("""INSERT INTO transactions(user_id,kind,amount,balance_after,note)
                     SELECT u.id,'OPENING_BALANCE',u.balance,u.balance,'Preserved balance during persistence migration'
                     FROM users u
                     WHERE ABS(u.balance)>0.005
                       AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.user_id=u.id)""")
        c.execute("""UPDATE users SET balance=ROUND((SELECT SUM(t.amount) FROM transactions t WHERE t.user_id=users.id),2)
                     WHERE EXISTS (SELECT 1 FROM transactions t WHERE t.user_id=users.id)
                       AND ABS(balance-(SELECT SUM(t.amount) FROM transactions t WHERE t.user_id=users.id))>0.005""")
@contextmanager
def connect():
    c=sqlite3.connect(DB_PATH,timeout=30)
    c.row_factory=sqlite3.Row
    c.execute('PRAGMA busy_timeout=30000')
    c.execute('PRAGMA foreign_keys=ON')
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA synchronous=FULL')
    try: yield c; c.commit()
    except: c.rollback(); raise
    finally: c.close()
def one(q,p=()):
    with connect() as c:return c.execute(q,p).fetchone()
def all(q,p=()):
    with connect() as c:return c.execute(q,p).fetchall()
def run(q,p=()):
    with connect() as c:
        x=c.execute(q,p); return x.lastrowid
def user(tg,ref=None):
    with connect() as c:
        r=c.execute('SELECT * FROM users WHERE id=?',(tg.id,)).fetchone()
        if not r:
            safe_ref=ref if ref and ref!=tg.id and c.execute('SELECT 1 FROM users WHERE id=?',(ref,)).fetchone() else None
            c.execute('INSERT INTO users(id,username,first_name,referral_id) VALUES(?,?,?,?)',(tg.id,tg.username,tg.first_name,safe_ref))
            if safe_ref:
                c.execute('INSERT OR IGNORE INTO referrals(referrer_id,referred_id,qualified,reward) VALUES(?,?,0,0)',(safe_ref,tg.id))
        else:c.execute('UPDATE users SET username=?,first_name=? WHERE id=?',(tg.username,tg.first_name,tg.id))
def is_admin(uid):return bool(one('SELECT 1 FROM admins WHERE user_id=?',(uid,)))
def is_super(uid):return bool(one("SELECT 1 FROM admins WHERE user_id=? AND role='SUPER_ADMIN'",(uid,)))
def admin_role(uid):
 r=one('SELECT role FROM admins WHERE user_id=?',(uid,)); return r['role'] if r else None
def is_scanner_admin(uid):return admin_role(uid) in ('SCANNER_ADMIN','ADMIN','SUPER_ADMIN')
def is_full_admin(uid):return admin_role(uid) in ('ADMIN','SUPER_ADMIN')
def credit(uid,amount,kind,note):
    with connect() as c:
        r=c.execute('SELECT balance FROM users WHERE id=?',(uid,)).fetchone(); b=round(r['balance']+amount,2)
        c.execute('UPDATE users SET balance=? WHERE id=?',(b,uid)); c.execute('INSERT INTO transactions(user_id,kind,amount,balance_after,note) VALUES(?,?,?,?,?)',(uid,kind,amount,b,note)); return b
def debit(uid,amount,note):return credit(uid,-amount,'DEBIT',note)
def create_local(uid,service_id,target,quantity,amount,status='PENDING_APPROVAL'):
    return run('INSERT INTO orders(user_id,service_id,target,quantity,amount,status) VALUES(?,?,?,?,?,?)',(uid,service_id,target,quantity,amount,status))


# keyboards
def back(): return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ BACK", callback_data="back")]])
def dashboard():
 return InlineKeyboardMarkup([[InlineKeyboardButton("💰 BALANCE",callback_data="balance")],[InlineKeyboardButton("📦 SERVICES",callback_data="services"),InlineKeyboardButton("🧾 MY ORDERS",callback_data="orders")],[InlineKeyboardButton("🔎 TRACK ORDER",callback_data="track"),InlineKeyboardButton("👤 PROFILE",callback_data="profile")],[InlineKeyboardButton("💳 DEPOSIT",callback_data="deposit"),InlineKeyboardButton("🎉 REFER",callback_data="refer")],[InlineKeyboardButton("🛟 SUPPORT",callback_data="support"),InlineKeyboardButton("🎁 REDEEM CODE",callback_data="redeem")],[InlineKeyboardButton("📊 STATISTICS",callback_data="stats"),InlineKeyboardButton("🎟️ PROMO CODE",callback_data="promo")],[InlineKeyboardButton("🎁 BONUS",callback_data="bonus")],[InlineKeyboardButton("⚙️ SETTINGS",callback_data="settings")]])
def admin_panel():
 return InlineKeyboardMarkup([[InlineKeyboardButton("👥 USERS",callback_data="a_users"),InlineKeyboardButton("📦 ORDERS",callback_data="a_orders")],[InlineKeyboardButton("💳 DEPOSITS",callback_data="a_deposits"),InlineKeyboardButton("🖥 SERVERS",callback_data="a_servers")],[InlineKeyboardButton("🛒 SERVICES",callback_data="a_services"),InlineKeyboardButton("📢 CHANNELS",callback_data="a_channels")],[InlineKeyboardButton("🎁 REDEEM",callback_data="a_redeem"),InlineKeyboardButton("📊 STATISTICS",callback_data="a_stats")],[InlineKeyboardButton("🎁 REFERRAL",callback_data="a_referral"),InlineKeyboardButton("⚙️ SETTINGS",callback_data="a_settings")],[InlineKeyboardButton("👮 ADMINS",callback_data="a_admins")],[InlineKeyboardButton("📲 SCANNER ADMINS",callback_data="a_scanner_admins")],[InlineKeyboardButton("🧾 SCANNER QR",callback_data="a_scanner_qr")],[InlineKeyboardButton("📣 BROADCAST",callback_data="a_broadcast"),InlineKeyboardButton("💬 SUPPORT",callback_data="a_support"),InlineKeyboardButton("🤖 AI SETTINGS",callback_data="a_ai")]])

def migrate_order_columns():
    try:
        with connect() as c:
            cols={r['name'] for r in c.execute('PRAGMA table_info(orders)').fetchall()}
            if 'refund_issued' not in cols:
                c.execute('ALTER TABLE orders ADD COLUMN refund_issued INTEGER DEFAULT 0')
    except Exception:
        log.exception('orders table migration failed')


def amount(s):
 try:
  x=float(s); return x if 0<x<=10000000 else None
 except: return None
def normalize_channel_ref(value):
 s=str(value or '').strip()
 if s.startswith(('https://t.me/','http://t.me/','https://telegram.me/','http://telegram.me/')):
  s=s.split('://',1)[1].split('/',1)[1].split('?',1)[0].strip('/')
  s='@'+s.lstrip('@')
 if s.startswith('@') and len(s)>1 and ' ' not in s:return s
 if s.lstrip('-').isdigit():return s
 return None
def order_price(s,q): return round(float(s["selling_price"])*q/1000,2)
def wallet_balance(uid): return float(one("SELECT balance FROM users WHERE id=?",(uid,))["balance"])
def setting(key, default=''):
 r=one('SELECT value FROM settings WHERE key=?',(key,)); return r['value'] if r else default
def ai_config():
 return setting('ai_api_url',AI_API_URL).strip(), setting('ai_api_key',AI_API_KEY).strip(), setting('ai_model',AI_MODEL).strip() or 'gpt-4o-mini'
async def ai_complete(prompt):
 url,key,model=ai_config()
 if not url or not key: raise RuntimeError('AI API is not configured. Admin must configure it first.')
 endpoint=url.rstrip('/')
 if not endpoint.endswith('/chat/completions'): endpoint += '/chat/completions'
 headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'}
 payload={'model':model,'messages':[{'role':'system','content':'You are a concise assistant for a Telegram SMM bot administrator. Do not invent credentials or claim an action was completed unless the bot completed it.'},{'role':'user','content':prompt}], 'temperature':0.2, 'max_tokens':700}
 async with httpx.AsyncClient(timeout=45) as client:
  response=await client.post(endpoint,headers=headers,json=payload)
  response.raise_for_status(); data=response.json()
 try:return data['choices'][0]['message']['content'].strip()
 except (KeyError,IndexError,TypeError):raise RuntimeError('AI API returned an unexpected response.')
def charge(uid,a,note):
 if wallet_balance(uid)<a:return False
 credit(uid,-a,"DEBIT",note);return True


import httpx

class GenericSMM:
 def __init__(self,url,key):self.url=url.rstrip('/');self.key=key
 async def call(self,action,**kw):
  if not self.key: raise RuntimeError('Provider API key is not configured')
  async with httpx.AsyncClient(timeout=30) as c:
   r=await c.post(self.url,data={'key':self.key,'action':action,**kw}); r.raise_for_status(); data=r.json()
   if isinstance(data,dict) and data.get('error'):raise RuntimeError(str(data['error']))
   return data
 async def get_services(self):return await self.call('services')
 async def get_balance(self):return await self.call('balance')
 async def create_order(self,service_id,target,quantity):return await self.call('add',service=service_id,link=target,quantity=quantity)
 async def get_order_status(self,order_id):return await self.call('status',order=order_id)
 async def cancel_order(self,order_id):return await self.call('cancel',order=order_id)
 async def refill_order(self,order_id):return await self.call('refill',order=order_id)


DEP_AMOUNT,DEP_UTR,DEP_SCREEN,TARGET,QTY,SUPPORT_TEXT=range(6)
async def blocked(update):
 r=one('SELECT blocked FROM users WHERE id=?',(update.effective_user.id,)); return r and r['blocked']
def ref_arg(context):
 if context.args and context.args[0].startswith('ref_'):
  try:return int(context.args[0][4:])
  except:return None
def channel_verified(uid):
 r=one('SELECT channel_verified FROM users WHERE id=?',(uid,))
 return bool(r and r['channel_verified'])
async def start(update,context):
 user(update.effective_user,ref_arg(context)); await gate(update,context)
async def gate(update,context):
 uid=update.effective_user.id
 if setting('channel_gate_enabled','1').lower() in ('0','off','false','no') or channel_verified(uid):
  return await show_dashboard(update)
 chans=all('SELECT * FROM channels WHERE active=1')
 if chans:
  rows=[[InlineKeyboardButton('📢 JOIN CHANNEL',url=x['invite_url'])] for x in chans]
  rows.append([InlineKeyboardButton('✅ VERIFY',callback_data='verify')])
  text='कृपया सभी अनिवार्य channels join करके VERIFY दबाएँ।'
  if update.callback_query: await update.callback_query.edit_message_text(text,reply_markup=InlineKeyboardMarkup(rows))
  else: await update.message.reply_text(text,reply_markup=InlineKeyboardMarkup(rows))
 else: await show_dashboard(update)
async def verify(update,context):
 q=update.callback_query; bad=[]; errors=[]
 bot_id=(await context.bot.get_me()).id
 channels=all('SELECT * FROM channels WHERE active=1 ORDER BY id')
 if not channels:
  return await q.edit_message_text('❌ कोई mandatory channel configured नहीं है। Admin Panel → CHANNELS में channels add करें।',reply_markup=back())
 for c in channels:
  try:
   # Accept @username, numeric -100… IDs, or a t.me link; resolve before member checks.
   channel_ref=normalize_channel_ref(c['channel_id'])
   if not channel_ref:
    errors.append(f"{c['name']} (invalid channel ID/username)")
    continue
   chat=await context.bot.get_chat(channel_ref)
   bot_member=await context.bot.get_chat_member(chat_id=chat.id,user_id=bot_id)
   if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.OWNER):
    errors.append(f"{c['name']} (bot admin नहीं है)")
    continue
   m=await context.bot.get_chat_member(chat_id=chat.id,user_id=q.from_user.id)
   is_member=(m.status in (ChatMemberStatus.MEMBER,ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.OWNER) or (m.status==ChatMemberStatus.RESTRICTED and bool(getattr(m,'is_member',False))))
   if not is_member: bad.append(c['name'])
  except Exception as exc:
   log.warning('Channel verification failed for %s (%s): %s',c['name'],c['channel_id'],exc)
   errors.append(f"{c['name']} (channel ID/username या bot access गलत)")
 if bad or errors:
  names=', '.join(bad+errors)
  extra='\n\nAdmin Panel → CHANNELS में public @username या numeric -100… channel ID रखें। Invite URL केवल join button के लिए है। हर channel में bot को Administrator बनाकर VERIFY AGAIN दबाएं।'
  return await q.edit_message_text('❌ Verification पूरी नहीं हुई।\nजाँच में समस्या: '+names+extra,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔄 VERIFY AGAIN',callback_data='verify')],[InlineKeyboardButton('⬅️ BACK',callback_data='back')]]))
 run('UPDATE users SET channel_verified=1 WHERE id=?',(q.from_user.id,))
 await show_dashboard(update)

async def show_dashboard(update):
 uid=update.effective_user.id; txt=f'💰 BALANCE\n₹{wallet_balance(uid):.2f}\n\nScorpio SMM Panel\nनीचे menu चुनें।'
 if update.callback_query:await update.callback_query.edit_message_text(txt,reply_markup=dashboard())
 else:await update.message.reply_text(txt,reply_markup=dashboard())
async def menu(update,context):
 user(update.effective_user); await show_dashboard(update)
async def cb(update,context):
 q=update.callback_query; await q.answer(); d=q.data; uid=q.from_user.id
 if d.startswith('a_') or d.startswith('asvc:') or d.startswith('create_') or d.startswith('redeem_view:') or d.startswith('ai_') or d.startswith('approve:') or d.startswith('reject:') or d.startswith('order_approve:') or d.startswith('order_reject:') or d.startswith('ch') or d.startswith('scanner_qr_'):
  if not (is_admin(uid) and context.user_data.get('admin_authenticated')): return await q.edit_message_text('🔐 पहले /admin चलाकर password verify करें।')
  if admin_role(uid)=='SCANNER_ADMIN' and d not in ('a_deposits','a_scanner_qr') and not d.startswith(('approve:','reject:','scanner_qr_')):
   return await q.edit_message_text('🔐 Scanner Admin को केवल DEPOSITS/QR access दिया गया है।',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('💳 DEPOSITS',callback_data='a_deposits')]]))
 if d=='verify':return await verify(update,context)
 if d=='back':
  if is_admin(uid) and context.user_data.get('admin_authenticated'):
   return await q.edit_message_text('⚙️ ADMIN PANEL',reply_markup=admin_panel())
  return await show_dashboard(update)
 if d=='services':
  cats=all("SELECT category,COUNT(*) n FROM services WHERE active=1 GROUP BY category")
  return await q.edit_message_text('📦 SERVICES\nCategory चुनें:',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(x['category'],callback_data='cat:'+x['category'])] for x in cats]+[[InlineKeyboardButton('⬅️ BACK',callback_data='back')]]))
 if d.startswith('cat:'):
  ss=all('SELECT * FROM services WHERE active=1 AND category=?',(d[4:],)); rows=[[InlineKeyboardButton(f"{s['name']} | ₹{s['selling_price']}/1k",callback_data=f"svc:{s['id']}")] for s in ss];rows.append([InlineKeyboardButton('⬅️ BACK',callback_data='services')]);return await q.edit_message_text('Service चुनें:',reply_markup=InlineKeyboardMarkup(rows))
 if d.startswith('svc:'):
  s=one('SELECT * FROM services WHERE id=?',(int(d[4:]),)); context.user_data['service']=s; context.user_data['stage']='target'; await q.edit_message_text(f"{s['name']}\n{s['description'] or 'No description'}\nRange: {s['min_qty']}-{s['max_qty']}\nTarget URL भेजें:",reply_markup=back());return TARGET
 if d=='balance': return await q.edit_message_text(f'💰 WALLET\nAvailable Balance: ₹{wallet_balance(uid):.2f}\nTotal Deposited: ₹{one("SELECT COALESCE(SUM(amount),0) x FROM transactions WHERE user_id=? AND kind=\'DEPOSIT\'",(uid,))["x"]:.2f}\nTotal Spent: ₹{abs(one("SELECT COALESCE(SUM(amount),0) x FROM transactions WHERE user_id=? AND kind=\'DEBIT\'",(uid,))["x"]):.2f}',reply_markup=back())
 if d=='bonus':
  b=one("SELECT * FROM bonuses WHERE key='welcome' AND active=1")
  if not b:return await q.edit_message_text('No bonus is active.',reply_markup=back())
  if one("SELECT 1 FROM bonus_claims WHERE key='welcome' AND user_id=?",(uid,)):return await q.edit_message_text('Bonus already claimed.',reply_markup=back())
  run("INSERT INTO bonus_claims(key,user_id) VALUES('welcome',?)",(uid,));credit(uid,b['value'],'BONUS','welcome bonus');return await q.edit_message_text(f'🎁 ₹{b["value"]:.2f} bonus credited.',reply_markup=back())
 if d=='deposit':context.user_data.clear();context.user_data['stage']='deposit';return await q.edit_message_text('💳 Deposit amount भेजें (₹1 या उससे अधिक):',reply_markup=back())
 if d=='orders':
  rs=all('SELECT o.*,s.name FROM orders o JOIN services s ON s.id=o.service_id WHERE o.user_id=? ORDER BY o.id DESC LIMIT 10',(uid,));return await q.edit_message_text('🧾 MY ORDERS\n'+'\n'.join(f"#{x['id']} {x['name']} ₹{x['amount']:.2f} {x['status']}" for x in rs) or 'No orders yet',reply_markup=back())
 if d=='profile':
  u=one('SELECT * FROM users WHERE id=?',(uid,));n=one('SELECT COUNT(*) n FROM orders WHERE user_id=?',(uid,))['n'];return await q.edit_message_text(f"👤 PROFILE\nUser ID: {uid}\nUsername: @{u['username'] or '-'}\nRegistered: {u['registered_at']}\nBalance: ₹{u['balance']:.2f}\nOrders: {n}",reply_markup=back())
 if d=='refer':
  me=(await context.bot.get_me()).username
  reward=float(setting('referral_reward','0') or 0)
  total=one('SELECT COUNT(*) n FROM referrals WHERE referrer_id=?',(uid,))['n']
  earned=one("SELECT COALESCE(SUM(reward),0) x FROM referrals WHERE referrer_id=? AND qualified=1",(uid,))['x']
  return await q.edit_message_text(f'🎉 REFER\nआपका referral link:\nhttps://t.me/{me}?start=ref_{uid}\n\n💰 Current reward: ₹{reward:.2f} per successful referral\n👥 Total referrals: {total}\n💵 Total earned: ₹{float(earned):.2f}',reply_markup=back())
 if d=='stats':
  n=one('SELECT COUNT(*) n FROM orders WHERE user_id=?',(uid,))['n'];sp=one("SELECT COALESCE(SUM(amount),0) x FROM transactions WHERE user_id=? AND kind='DEBIT'",(uid,))['x'];return await q.edit_message_text(f'📊 STATISTICS\nTotal Orders: {n}\nTotal Spent: ₹{sp:.2f}',reply_markup=back())
 if d=='support':context.user_data['stage']='support';return await q.edit_message_text('🛟 अपना support message भेजें:',reply_markup=back())
 if d=='track':
  return await q.edit_message_text('🔎 अपना order ID भेजें, जैसे: 123',reply_markup=back())
 if d=='promo':
  return await q.edit_message_text('🎟️ Promo code सुविधा जल्द उपलब्ध होगी।',reply_markup=back())
 if d=='settings':
  return await q.edit_message_text('⚙️ Settings अभी admin द्वारा manage की जाती हैं।',reply_markup=back())
 if d=='redeem':context.user_data['stage']='redeem';return await q.edit_message_text('🎁 Redeem code भेजें:',reply_markup=back())
 if d=='a_channels' and is_admin(uid):
  chans=all('SELECT * FROM channels ORDER BY id DESC')
  rows=[[InlineKeyboardButton(f"{'🟢' if x['active'] else '🔴'} {x['name']}",callback_data=f"chview:{x['id']}")] for x in chans]
  rows += [[InlineKeyboardButton('➕ ADD CHANNEL',callback_data='chadd')],[InlineKeyboardButton('⬅️ BACK',callback_data='admin')]]
  return await q.edit_message_text('📢 CHANNEL MANAGEMENT\nExisting mandatory channels:',reply_markup=InlineKeyboardMarkup(rows))
 if d=='chadd' and is_admin(uid):
  context.user_data['channel_stage']='name';return await q.edit_message_text('Channel का नाम भेजें:',reply_markup=back())
 if d.startswith('chview:') and is_admin(uid):
  c=one('SELECT * FROM channels WHERE id=?',(int(d[7:]),))
  if not c:return await q.answer('Channel not found',show_alert=True)
  return await q.edit_message_text(f"📢 {c['name']}\nID: {c['channel_id']}\nInvite: {c['invite_url']}\nStatus: {'ACTIVE' if c['active'] else 'INACTIVE'}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🟢/🔴 TOGGLE',callback_data=f'chtoggle:{c["id"]}'),InlineKeyboardButton('✏️ EDIT',callback_data=f'chedit:{c["id"]}'),InlineKeyboardButton('🗑 DELETE',callback_data=f'chdelete:{c["id"]}')],[InlineKeyboardButton('⬅️ BACK',callback_data='a_channels')]]))
 if d.startswith('chtoggle:') and is_admin(uid):
  cid=int(d[9:]);run('UPDATE channels SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(cid,));return await q.edit_message_text('✅ Channel status updated.',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ BACK',callback_data='a_channels')]]))
 if d.startswith('chedit:') and is_admin(uid):
  cid=int(d[7:]); c=one('SELECT * FROM channels WHERE id=?',(cid,))
  if not c:return await q.answer('Channel not found',show_alert=True)
  context.user_data.update(channel_stage='edit_name',edit_channel_id=cid,channel_name=c['name'],channel_id=c['channel_id'],invite_url=c['invite_url'])
  return await q.edit_message_text('✏️ नया channel name भेजें:',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_channels')]]))
 if d.startswith('chdelete:') and is_admin(uid):
  cid=int(d[9:]); deleted=run('DELETE FROM channels WHERE id=?',(cid,));return await q.edit_message_text('✅ Channel deleted.' if deleted else '❌ Channel not found.',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ BACK',callback_data='a_channels')]]))
 if d=='admin' and is_admin(uid) and context.user_data.get('admin_authenticated'):return await q.edit_message_text('⚙️ ADMIN PANEL',reply_markup=admin_panel())
 if d=='a_scanner_qr' and is_scanner_admin(uid):
  qrid=setting('qr_file_id','').strip()
  enabled=setting('qr_enabled','0').strip().lower() in ('1','true','yes','on')
  status='🟢 ACTIVE' if qrid and enabled else ('🟡 SAVED / DISABLED' if qrid else '🔴 NOT SET')
  rows=[[InlineKeyboardButton('➕ SET / REPLACE QR',callback_data='scanner_qr_set')]]
  if qrid:
   rows.append([InlineKeyboardButton('⏸ DISABLE QR',callback_data='scanner_qr_disable'),InlineKeyboardButton('🗑 REMOVE QR',callback_data='scanner_qr_remove')])
  rows.append([InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')])
  return await q.edit_message_text(f'🧾 SCANNER QR\nStatus: {status}\n\nQR ACTIVE होने पर user Deposit में amount भेजते ही यही payment scanner मिलेगा।',reply_markup=InlineKeyboardMarkup(rows))
 if d=='scanner_qr_set' and is_scanner_admin(uid):
  context.user_data['scanner_qr_stage']=True
  return await q.edit_message_text('🧾 SCANNER QR SETUP\nPayphone, Paytm, Google Pay या किसी भी UPI app का QR photo भेजें।\nयह QR पुराने QR को replace करेगा और यही active QR users के Deposit में दिखेगा।',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_scanner_qr')]]))
 if d=='scanner_qr_disable' and is_scanner_admin(uid):
  run("INSERT INTO settings(key,value) VALUES('qr_enabled','0') ON CONFLICT(key) DO UPDATE SET value='0'")
  return await q.edit_message_text('⏸ Scanner QR disabled.\nUser Deposit में scanner नहीं दिखेगा।',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🧾 SCANNER QR',callback_data='a_scanner_qr')],[InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')]]))
 if d=='scanner_qr_remove' and is_scanner_admin(uid):
  run("INSERT INTO settings(key,value) VALUES('qr_enabled','0') ON CONFLICT(key) DO UPDATE SET value='0'")
  run("DELETE FROM settings WHERE key='qr_file_id'")
  context.user_data.pop('scanner_qr_stage',None)
  return await q.edit_message_text('🗑 Scanner QR removed.\nअब नया QR SET / REPLACE QR से कभी भी डाल सकते हैं।',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('➕ SET NEW QR',callback_data='scanner_qr_set')],[InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')]]))
 if d=='a_deposits' and is_admin(uid):return await pending_deposits(update,context)
 if d.startswith('approve:') and is_admin(uid):return await approve(update,context,int(d[8:]))
 if d.startswith('reject:') and is_admin(uid):return await reject(update,context,int(d[7:]))
 if d.startswith('order_approve:') and is_full_admin(uid):return await approve_order(update,context,int(d[14:]))
 if d.startswith('order_reject:') and is_full_admin(uid):return await reject_order(update,context,int(d[13:]))
 if d=='a_admins' and is_super(uid):
  rows=all('SELECT user_id,role FROM admins ORDER BY role,user_id')
  text='👮 ADMINS\\n'+'\\n'.join(f"{x['user_id']} ({x['role']})" for x in rows)
  kb=[[InlineKeyboardButton('➕ ADD ADMIN',callback_data='admin_add')],[InlineKeyboardButton('➖ REMOVE ADMIN',callback_data='admin_remove')],[InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')]]
  return await q.edit_message_text(text+'\\n\\nMaximum 4 additional ADMIN accounts.',reply_markup=InlineKeyboardMarkup(kb))
 if d=='a_scanner_admins' and is_super(uid):
  rows=all("SELECT user_id FROM admins WHERE role='SCANNER_ADMIN' ORDER BY user_id")
  text='📲 SCANNER ADMINS\\n'+('\\n'.join(f"{x['user_id']}" for x in rows) if rows else 'No scanner admins yet.')
  kb=[[InlineKeyboardButton('➕ ADD SCANNER ADMIN',callback_data='scanner_add')],[InlineKeyboardButton('➖ REMOVE SCANNER ADMIN',callback_data='scanner_remove')],[InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')]]
  return await q.edit_message_text(text+'\\n\\nScanner Admin payment QR और deposit approvals manage कर सकता है.',reply_markup=InlineKeyboardMarkup(kb))
 if d=='admin_add' and is_super(uid):
  context.user_data['admin_wizard']='add_admin'
  return await q.edit_message_text('👮 नया ADMIN जोड़ें।\\nTelegram USER ID या @username भेजें:',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_admins')]]))
 if d=='admin_remove' and is_super(uid):
  context.user_data['admin_wizard']='remove_admin'
  return await q.edit_message_text('➖ जिस ADMIN को हटाना है उसका Telegram USER ID भेजें:',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_admins')]]))
 if d=='scanner_add' and is_super(uid):
  context.user_data['admin_wizard']='add_scanner'
  return await q.edit_message_text('📲 Scanner Admin जोड़ें।\\nScanner का Telegram USER ID या @username भेजें:',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_scanner_admins')]]))
 if d=='scanner_remove' and is_super(uid):
  context.user_data['admin_wizard']='remove_scanner'
  return await q.edit_message_text('➖ जिस Scanner Admin को हटाना है उसका Telegram USER ID भेजें:',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_scanner_admins')]]))

 if d.startswith('admin:') and is_admin(uid):return await q.edit_message_text('Admin action received. Use documented commands for configuration.',reply_markup=admin_panel())
 if d=='a_stats' and is_admin(uid):
  return await q.edit_message_text(f"Users: {one('SELECT COUNT(*) n FROM users')['n']}\nOrders: {one('SELECT COUNT(*) n FROM orders')['n']}\nDeposits: {one('SELECT COUNT(*) n FROM deposits')['n']}",reply_markup=back())
 if d=='a_users' and is_admin(uid):
  n=one('SELECT COUNT(*) n FROM users')['n']; blocked_n=one('SELECT COUNT(*) n FROM users WHERE blocked=1')['n']
  return await q.edit_message_text(f'👥 USERS\\nTotal: {n}\\nBlocked: {blocked_n}\\n\\nCommands: /block ID, /unblock ID, /adjustbalance ID amount',reply_markup=back())
 if d=='a_orders' and is_admin(uid):
  rows=all('SELECT id,user_id,amount,status,created_at FROM orders ORDER BY id DESC LIMIT 15')
  text='📦 ORDERS\\n'+'\\n'.join(f"#{x['id']} | user {x['user_id']} | ₹{x['amount']:.2f} | {x['status']}" for x in rows)
  return await q.edit_message_text(text if rows else '📦 ORDERS\\nNo orders yet.',reply_markup=back())
 if d=='a_servers' and is_admin(uid):
  rows=all('SELECT id,name,active,priority FROM providers ORDER BY priority,id')
  text='🖥 SERVERS\\n'+'\\n'.join(f"#{x['id']} {x['name']} | {'ON' if x['active'] else 'OFF'} | priority {x['priority']}" for x in rows)
  return await q.edit_message_text(text if rows else '🖥 SERVERS\\nNo providers configured.\\nUse /servers and provider setup in database.',reply_markup=back())
 if d=='a_services' and is_admin(uid):
  services=all('SELECT id,name,category,selling_price,active FROM services ORDER BY id LIMIT 30')
  rows=[[InlineKeyboardButton(f"{'🟢' if x['active'] else '🔴'} {x['name']} | ₹{x['selling_price']}/1k",callback_data=f"asvc:{x['id']}")] for x in services]
  rows.append([InlineKeyboardButton('➕ CREATE PLATFORM SERVICES',callback_data='create_service')])
  rows.append([InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')])
  return await q.edit_message_text('🛒 SERVICES\\nकिसी service पर tap करके status बदलें या नया platform setup करें।' if services else '🛒 SERVICES\\nअभी कोई service नहीं है। नया platform setup करें।',reply_markup=InlineKeyboardMarkup(rows))
 if d=='create_service' and is_admin(uid):
  context.user_data.pop('stage',None);context.user_data['admin_wizard']='services';context.user_data['service_step']='platform'
  return await q.edit_message_text('🛒 नया platform setup करें।\\nकौन सा platform चाहिए?\\nInstagram, Facebook, YouTube या Telegram लिखें:',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_services')]]))
 if d.startswith('redeem_view:') and is_admin(uid):
  code=d[12:]; item=one('SELECT * FROM redeem_codes WHERE code=?',(code,))
  if not item:return await q.answer('Code not found',show_alert=True)
  return await q.edit_message_text(f"🎁 {item['code']}\\nReward: ₹{item['reward']:.2f}\\nUsage limit: {item['usage_limit']}\\nExpiry: {item['expires_at'] or '-'}\\nStatus: {'ACTIVE' if item['active'] else 'INACTIVE'}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ BACK TO CODES',callback_data='a_redeem')]]))
 if d.startswith('asvc:') and is_admin(uid):
  sid=int(d[5:]); service=one('SELECT * FROM services WHERE id=?',(sid,))
  if not service:return await q.answer('Service not found',show_alert=True)
  run('UPDATE services SET active=CASE active WHEN 1 THEN 0 ELSE 1 END WHERE id=?',(sid,))
  service=one('SELECT * FROM services WHERE id=?',(sid,))
  return await q.edit_message_text(f"✅ Service updated\\n{service['name']}\\nStatus: {'ACTIVE' if service['active'] else 'INACTIVE'}",reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('⬅️ BACK TO SERVICES',callback_data='a_services')],[InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')]]))
 if d=='a_redeem' and is_admin(uid):
  rows=all('SELECT code,reward,usage_limit,expires_at,active FROM redeem_codes ORDER BY code LIMIT 30')
  text='🎁 REDEEM CODES\\n'+'\\n'.join(f"{x['code']} | ₹{x['reward']:.2f} | limit {x['usage_limit']} | expires {x['expires_at'] or '-'} | {'ON' if x['active'] else 'OFF'}" for x in rows)
  buttons=[[InlineKeyboardButton('➕ CREATE REDEEM CODE',callback_data='create_redeem')]]
  buttons += [[InlineKeyboardButton(f"{x['code']} | ₹{x['reward']:.2f}",callback_data=f"redeem_view:{x['code']}")] for x in rows]
  buttons.append([InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')])
  return await q.edit_message_text(text if rows else '🎁 REDEEM CODES\\nअभी कोई code नहीं है।',reply_markup=InlineKeyboardMarkup(buttons))
 if d=='create_redeem' and is_admin(uid):
  context.user_data.pop('stage',None);context.user_data['admin_wizard']='redeem_code';context.user_data['redeem_step']='code'
  return await q.edit_message_text('🎁 नया Redeem Code बनाने का wizard शुरू।\\nपहले code लिखें (जैसे WELCOME100):',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_redeem')]]))
 if d=='a_referral' and is_admin(uid):
  reward=float(setting('referral_reward','0') or 0)
  total=one('SELECT COUNT(*) n FROM referrals WHERE qualified=1')['n']
  paid=one('SELECT COALESCE(SUM(reward),0) x FROM referrals WHERE qualified=1')['x']
  return await q.edit_message_text(f'🎁 REFERRAL SETTINGS\n\n💰 Reward per successful referral: ₹{reward:.2f}\n👥 Qualified referrals: {total}\n💵 Total referral rewards paid: ₹{float(paid):.2f}',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✏️ SET REFERRAL REWARD',callback_data='referral_set')],[InlineKeyboardButton('🔄 REFRESH',callback_data='a_referral')],[InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')]]))
 if d=='referral_set' and is_admin(uid):
  context.user_data.pop('stage',None);context.user_data['admin_wizard']='referral_reward'
  return await q.edit_message_text('💰 Referral reward set करें।\nहर successful referral पर कितने रुपये देने हैं?\nExample: 10',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_referral')]]))
 if d=='a_settings' and is_admin(uid):
  rows=all('SELECT key,value FROM settings ORDER BY key')
  text='⚙️ SETTINGS\\n'+'\\n'.join(f"{x['key']}: {x['value']}" for x in rows)
  return await q.edit_message_text(text if rows else '⚙️ SETTINGS\\nNo settings saved.\\nUse /set key | value',reply_markup=back())
 if d=='a_ai' and is_admin(uid):
  url,key,model=ai_config(); masked=(key[:4]+'...' + key[-4:]) if len(key)>=10 else ('SET' if key else 'NOT SET')
  return await q.edit_message_text(f'🤖 AI SETTINGS\\nURL: {url or "NOT SET"}\\nKey: {masked}\\nModel: {model}',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('🔧 CONFIGURE AI API',callback_data='ai_setup')],[InlineKeyboardButton('💬 AI ASSISTANT',callback_data='ai_assist')],[InlineKeyboardButton('⬅️ ADMIN PANEL',callback_data='admin')]]))
 if d=='ai_setup' and is_admin(uid):
  context.user_data.pop('stage',None);context.user_data['admin_wizard']='ai_settings';context.user_data['ai_step']='url'
  return await q.edit_message_text('🤖 AI API setup शुरू।\\nOpenAI-compatible API URL भेजें (जैसे https://api.openai.com/v1):',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_ai')]]))
 if d=='ai_assist' and is_admin(uid):
  context.user_data.pop('stage',None);context.user_data['admin_wizard']='ai_assist'
  return await q.edit_message_text('💬 AI assistant को अपना सवाल भेजें। यह केवल admin के लिए है।\\nउदाहरण: Instagram followers के लिए pricing plan सुझाओ।',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('❌ CANCEL',callback_data='a_ai')]]))
 if d=='a_broadcast' and is_admin(uid):
  return await q.edit_message_text('📣 BROADCAST\\nBroadcast command अभी उपलब्ध नहीं है।',reply_markup=back())
 if d=='a_support' and is_admin(uid):
  rows=all("SELECT id,user_id,message,status FROM support_messages WHERE status='OPEN' ORDER BY id DESC LIMIT 15")
  text='💬 SUPPORT\\n'+'\\n'.join(f"#{x['id']} | user {x['user_id']} | {x['message'][:80]}" for x in rows)
  return await q.edit_message_text(text if rows else '💬 SUPPORT\\nNo open tickets.',reply_markup=back())
 return await q.edit_message_text('यह button अभी उपलब्ध नहीं है। /menu या /admin से वापस जाएँ।',reply_markup=back())
async def text(update,context):
 uid=update.effective_user.id; t=update.message.text.strip()
 if context.user_data.get("admin_password_pending"):
  if not is_admin(uid): return await update.message.reply_text("Unauthorized")
  if is_super(uid) and (t.isdigit() or t.startswith('@')) and t != ADMIN_PASSWORD:
   context.user_data.pop("admin_password_pending",None)
   return await add_admin_target(update,context,t)
  if t == ADMIN_PASSWORD:
   context.user_data.pop("admin_password_pending",None); context.user_data["admin_authenticated"] = True
   return await update.message.reply_text("✅ Admin login successful", reply_markup=admin_panel())
  context.user_data.pop("admin_password_pending",None)
  return await update.message.reply_text("❌ गलत password. फिर से /admin चलाएँ।")
 if context.user_data.get('admin_wizard'):
  if not (is_admin(uid) and context.user_data.get('admin_authenticated')):
   context.user_data.clear(); return await update.message.reply_text('Unauthorized')
  wizard=context.user_data['admin_wizard']
  if wizard=='add_admin':
   await add_admin_target(update,context,t); context.user_data.pop('admin_wizard',None); return
  if wizard=='add_scanner':
   await add_scanner_target(update,context,t); context.user_data.pop('admin_wizard',None); return
  if wizard=='remove_admin':
   await remove_admin_target(update,context,t); context.user_data.pop('admin_wizard',None); return
  if wizard=='remove_scanner':
   await remove_scanner_target(update,context,t); context.user_data.pop('admin_wizard',None); return
  if wizard=='referral_reward':
   try: reward=float(t)
   except ValueError: reward=-1
   if reward < 0 or reward > 1000000:
    return await update.message.reply_text('❌ Reward ₹0 से ₹10,00,000 के बीच रखें।')
   run('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('referral_reward',f'{reward:.2f}'))
   context.user_data.clear()
   return await update.message.reply_text(f'✅ Referral reward saved: ₹{reward:.2f} per successful referral.',reply_markup=admin_panel())
  step=context.user_data.get('redeem_step') or context.user_data.get('service_step')
  if wizard=='redeem_code':
   if step=='code':
    code=t.upper().replace(' ','')
    if not code.isalnum() or len(code)<3:return await update.message.reply_text('Code में कम से कम 3 letters/numbers रखें। फिर से लिखें:')
    context.user_data.update(redeem_code=code,redeem_step='reward')
    return await update.message.reply_text('इस code से user को कितने रुपये मिलेंगे? (जैसे 50)')
   if step=='reward':
    reward=amount(t)
    if not reward:return await update.message.reply_text('सही रुपये की राशि लिखें, जैसे 50:')
    context.user_data.update(redeem_reward=reward,redeem_step='limit')
    return await update.message.reply_text('यह code कुल कितने users use कर सकेंगे? (जैसे 100)')
   if step=='limit':
    try:limit=int(t)
    except ValueError:limit=0
    if limit<1:return await update.message.reply_text('Users की संख्या 1 या उससे अधिक लिखें:')
    context.user_data.update(redeem_limit=limit,redeem_step='expiry')
    return await update.message.reply_text('Expiry कितने घंटे बाद होगी? (जैसे 24 या 720)')
   if step=='expiry':
    try:hours=int(t)
    except ValueError:hours=0
    if hours<1:return await update.message.reply_text('Expiry hours में 1 या उससे अधिक संख्या लिखें:')
    expiry=(datetime.now(timezone.utc)+timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S UTC')
    try:
     code=context.user_data['redeem_code']; reward_value=context.user_data['redeem_reward']; limit_value=context.user_data['redeem_limit']
     run('INSERT INTO redeem_codes(code,reward,usage_limit,expires_at) VALUES(?,?,?,?)',(code,reward_value,limit_value,expiry))
     context.user_data.clear()
     return await update.message.reply_text(f'✅ Redeem code बन गया।\\nCode: {code}\\nReward: ₹{reward_value:.2f}\\nUsers: {limit_value}\\nExpiry: {expiry}',reply_markup=admin_panel())
    except sqlite3.IntegrityError:
     context.user_data.clear();return await update.message.reply_text('❌ यह code पहले से मौजूद है। फिर से Create Redeem Code दबाएँ।',reply_markup=admin_panel())
  if wizard=='services':
   if step=='platform':
    platform=t.strip().title()
    if platform.lower() not in ('instagram','facebook','youtube','telegram'):
     return await update.message.reply_text('कृपया केवल Instagram, Facebook, YouTube या Telegram लिखें:')
    context.user_data.update(service_platform=platform,service_step='views')
    return await update.message.reply_text(f'{platform} Views का selling price प्रति 1000 कितना रखना है? (₹ में)')
   if step in ('views','subscribers','followers'):
    price=amount(t)
    if not price:return await update.message.reply_text('सही price लिखें, जैसे 25:')
    context.user_data[f'price_{step}']=price
    if step=='views':context.user_data['service_step']='subscribers';return await update.message.reply_text('Subscribers/Subscribe का price प्रति 1000 कितना रखना है? (₹ में)')
    if step=='subscribers':context.user_data['service_step']='followers';return await update.message.reply_text('Followers का price प्रति 1000 कितना रखना है? (₹ में)')
    platform=context.user_data['service_platform']
    provider=one('SELECT id FROM providers ORDER BY priority,id LIMIT 1')
    provider_id=provider['id'] if provider else run('INSERT INTO providers(name,api_url,api_key,currency,priority,active) VALUES(?,?,?,?,?,?)',('Manual Provider',SMM_API_URL,SMM_API_KEY,'INR',999,1))
    created=[]
    for metric,label in (('views','Views'),('subscribers','Subscribers'),('followers','Followers')):
     name=f'{platform} {label}'
     run('INSERT INTO services(provider_id,provider_service_id,name,category,description,cost_price,selling_price,min_qty,max_qty,active) VALUES(?,?,?,?,?,?,?,?,?,1)',(provider_id,f'{platform.lower()}_{metric}',name,platform,f'{label} service for {platform}',0,context.user_data[f'price_{metric}'],100,10000000))
     created.append(f'{name}: ₹{context.user_data[f"price_{metric}"]:.2f}/1k')
    context.user_data.clear()
    return await update.message.reply_text('✅ Platform services बन गईं।\\n'+'\\n'.join(created),reply_markup=admin_panel())
 if context.user_data.get('admin_wizard'):
  if not (is_admin(uid) and context.user_data.get('admin_authenticated')):
   context.user_data.clear(); return await update.message.reply_text('Unauthorized')
  wizard=context.user_data['admin_wizard']
  if wizard=='ai_settings':
   step=context.user_data.get('ai_step')
   if step=='url':
    if not t.startswith('http://') and not t.startswith('https://'):
     return await update.message.reply_text('API URL http:// या https:// से शुरू होना चाहिए:')
    context.user_data.update(ai_url=t,ai_step='key')
    return await update.message.reply_text('अब AI API key भेजें। यह message में दोबारा नहीं दिखाई जाएगी:')
   if step=='key':
    if len(t)<8:return await update.message.reply_text('API key बहुत छोटी है। सही key भेजें:')
    context.user_data.update(ai_key=t,ai_step='model')
    return await update.message.reply_text('Model का नाम भेजें (खाली नहीं; जैसे gpt-4o-mini):')
   if step=='model':
    if len(t)<2:return await update.message.reply_text('Model का सही नाम भेजें:')
    run('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('ai_api_url',context.user_data['ai_url']))
    run('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('ai_api_key',context.user_data['ai_key']))
    run('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('ai_model',t))
    context.user_data.clear()
    return await update.message.reply_text('✅ AI API settings save हो गईं। अब AI ASSISTANT से test कर सकते हैं।',reply_markup=admin_panel())
  if wizard=='ai_assist':
   prompt=t
   context.user_data.clear()
   try:
    answer=await ai_complete(prompt)
    return await update.message.reply_text('🤖 AI RESPONSE\\n'+answer,reply_markup=admin_panel())
   except Exception as exc:
    log.warning('AI request failed: %s',exc)
    return await update.message.reply_text('❌ AI request failed। AI URL, API key और model जाँचें।',reply_markup=admin_panel())
 if context.user_data.get('channel_stage'):
  cs=context.user_data['channel_stage']
  if not (is_admin(uid) and context.user_data.get('admin_authenticated')): return await update.message.reply_text('Unauthorized')
  if cs=='name': context.user_data['channel_name']=t;context.user_data['channel_stage']='id';return await update.message.reply_text('Channel ID या @username भेजें (bot उस channel का admin होना चाहिए):')
  if cs=='id':
   channel_ref=normalize_channel_ref(t)
   if not channel_ref:return await update.message.reply_text('सही @channel_username, numeric -100… channel ID या t.me link भेजें:')
   context.user_data['channel_id']=channel_ref;context.user_data['channel_stage']='invite';return await update.message.reply_text('Invite URL भेजें (https://...):')
  if cs=='invite':
   if not t.startswith('https://'): return await update.message.reply_text('Invite URL https:// से शुरू होना चाहिए।')
   try:
    run('INSERT INTO channels(name,channel_id,invite_url,active) VALUES(?,?,?,1)',(context.user_data['channel_name'].strip(),context.user_data['channel_id'],t,))
    context.user_data.pop('channel_stage',None)
    return await update.message.reply_text('✅ Mandatory channel add हो गया। अब कुल active channels VERIFY में check होंगे।',reply_markup=admin_panel())
   except sqlite3.IntegrityError:
    return await update.message.reply_text('यह channel ID पहले से मौजूद है। कोई दूसरा channel ID दें:')
  if cs=='edit_name':
   context.user_data['channel_name']=t;context.user_data['channel_stage']='edit_id';return await update.message.reply_text('नया Channel ID या @username भेजें:')
  if cs=='edit_id':
   channel_ref=normalize_channel_ref(t)
   if not channel_ref:return await update.message.reply_text('सही @channel_username, numeric -100… channel ID या t.me link भेजें:')
   context.user_data['channel_id']=channel_ref;context.user_data['channel_stage']='edit_invite';return await update.message.reply_text('नया Invite URL भेजें (https://...):')
  if cs=='edit_invite':
   if not t.startswith('https://'):return await update.message.reply_text('Invite URL https:// से शुरू होना चाहिए।')
   try:
    run('UPDATE channels SET name=?,channel_id=?,invite_url=? WHERE id=?',(context.user_data['channel_name'],context.user_data['channel_id'],t,context.user_data['edit_channel_id']))
    context.user_data.clear();return await update.message.reply_text('✅ Channel details updated.',reply_markup=admin_panel())
   except sqlite3.IntegrityError:return await update.message.reply_text('यह channel ID किसी दूसरे channel में पहले से मौजूद है।')
 s= context.user_data.get('stage')
 if await blocked(update):return
 if s=='target':context.user_data['target']=t;context.user_data['stage']='qty';await update.message.reply_text('Quantity भेजें:');return
 if s=='qty':
  try:q=int(t)
  except:return await update.message.reply_text('Valid integer भेजें।')
  sv=context.user_data['service'];
  if not(sv['min_qty']<=q<=sv['max_qty']):return await update.message.reply_text('Quantity range के बाहर है।')
  a=order_price(sv,q);context.user_data.update(quantity=q,amount=a);context.user_data['stage']='confirm';return await update.message.reply_text(f'Price ₹{a:.2f}. Confirm करने के लिए YES लिखें।')
 if s=='confirm' and t.upper()=='YES':
  sv=context.user_data['service'];a=context.user_data['amount'];target=context.user_data['target'];quantity=context.user_data['quantity']
  if not charge(uid,a,'SMM order reserved for admin approval'):return await update.message.reply_text('❌ INSUFFICIENT BALANCE')
  oid=create_local(uid,sv['id'],target,quantity,a,'PENDING_APPROVAL')
  context.user_data.clear()
  await update.message.reply_text(f'✅ Order #{oid} admin approval के लिए भेज दिया गया है। Approval के बाद service process होगी।')
  order_text=(f'🆕 NEW SERVICE ORDER\\nOrder: #{oid}\\nUser: {uid}\\nService: {sv["name"]}\\n'
              f'Link: {target}\\nQuantity: {quantity}\\nAmount: ₹{a:.2f}\\nStatus: PENDING APPROVAL')
  for admin_row in all('SELECT user_id FROM admins WHERE role IN (\'ADMIN\',\'SUPER_ADMIN\')'):
   try:
    await context.bot.send_message(admin_row['user_id'],order_text,reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✅ CONFIRM ORDER',callback_data=f'order_approve:{oid}'),InlineKeyboardButton('❌ REJECT ORDER',callback_data=f'order_reject:{oid}')]]))
   except Exception:log.exception('service order admin notification failed for order %s',oid)
  return
 if s=='confirm':
  return await update.message.reply_text('Order confirm करने के लिए केवल YES लिखें, या /menu से वापस जाएँ।')
 if s=='deposit':
  a=amount(t)
  if a is None or a<1:return await update.message.reply_text('कृपया ₹1 या उससे अधिक सही amount लिखें, जैसे 100')
  qrid=setting('qr_file_id','').strip()
  qren=setting('qr_enabled','0').strip().lower() in ('1','true','yes','on')
  if not qrid or not qren:
   context.user_data['stage']='deposit'
   return await update.message.reply_text('❌ Payment scanner अभी configured नहीं है। Admin से QR upload करवाकर फिर amount भेजें।')
  try:
   # Keep the state at UTR only after Telegram confirms the QR message was sent.
   await update.message.reply_photo(photo=qrid,caption=f'💳 Deposit ₹{a:.2f}\\nइस active payment QR को scan करके Payphone/Paytm/Google Pay या अपनी UPI app से payment करें। Payment के बाद UTR भेजें:')
  except Exception:
   log.exception('Payment QR delivery failed for user %s',uid)
   context.user_data['stage']='deposit'
   return await update.message.reply_text('❌ Payment scanner भेजा नहीं जा सका। Admin से QR दोबारा upload करवाकर फिर amount भेजें।')
  context.user_data.update(dep_amount=a,stage='utr')
  return await update.message.reply_text('✅ Payment हो जाने के बाद अपना UTR / UPI Transaction ID भेजें:')
 if s=='utr':
  if len(t)<4:return await update.message.reply_text('कृपया सही UTR number भेजें:')
  context.user_data.update(utr=t,stage='screen')
  return await update.message.reply_text('📸 अब उसी payment का screenshot photo के रूप में भेजें।\nScreenshot में amount और transaction details साफ दिखनी चाहिए।')
 if s=='support':
  did=run('INSERT INTO support_messages(user_id,message) VALUES(?,?)',(uid,t));context.user_data.clear();return await update.message.reply_text(f'Support ticket #{did} admin को भेज दिया गया।',reply_markup=dashboard())
 if s=='redeem':
  c=one('SELECT * FROM redeem_codes WHERE code=? AND active=1',(t.upper(),));
  if not c:return await update.message.reply_text('Invalid या expired code')
  if c['expires_at']:
   try:
    expiry=datetime.strptime(c['expires_at'].replace(' UTC',''),'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc)>=expiry:return await update.message.reply_text('यह code expire हो चुका है।')
   except ValueError:pass
  used=one('SELECT COUNT(*) n FROM redeem_usage WHERE code=?',(t.upper(),))['n']
  if used>=c['usage_limit']:return await update.message.reply_text('इस code की usage limit पूरी हो चुकी है।')
  if one('SELECT 1 FROM redeem_usage WHERE code=? AND user_id=?',(t.upper(),uid)):return await update.message.reply_text('Code already used')
  run('INSERT INTO redeem_usage(code,user_id) VALUES(?,?)',(t.upper(),uid));credit(uid,c['reward'],'REDEEM',t.upper());context.user_data.clear();return await update.message.reply_text(f"₹{c['reward']:.2f} credited",reply_markup=dashboard())
async def photo(update,context):
 if context.user_data.get('scanner_qr_stage'):
  uid=update.effective_user.id
  if not (await admin_ok(update,context) and is_scanner_admin(uid)):
   context.user_data.pop('scanner_qr_stage',None)
   return await update.message.reply_text('Unauthorized')
  f=update.message.photo[-1].file_id
  run("INSERT INTO settings(key,value) VALUES('qr_file_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(f,))
  run("INSERT INTO settings(key,value) VALUES('qr_enabled','1') ON CONFLICT(key) DO UPDATE SET value='1'")
  context.user_data.pop('scanner_qr_stage',None)
  return await update.message.reply_text('✅ Payment QR saved + enabled.\\nअब users को Deposit में यही QR दिखेगा। Payphone, Paytm, Google Pay या किसी भी UPI QR को इसी तरह replace कर सकते हैं।\\nबाद में SCANNER QR → DISABLE या REMOVE से इसे बंद/हटा सकते हैं।',reply_markup=admin_panel())

 if context.user_data.get('stage')!='screen':return
 uid=update.effective_user.id;u=dict(context.user_data)
 if not u.get('dep_amount') or not u.get('utr') or not update.message.photo:
  return await update.message.reply_text('Deposit details अधूरे हैं। /start से deposit flow फिर शुरू करें।')
 try:
  did=run('INSERT INTO deposits(user_id,amount,utr,screenshot_file_id) VALUES(?,?,?,?)',(uid,u['dep_amount'],u['utr'],update.message.photo[-1].file_id))
 except sqlite3.IntegrityError:
  return await update.message.reply_text('यह UTR पहले submit हो चुका है। नया UTR भेजकर screenshot दोबारा submit करें।')
 context.user_data.clear();await update.message.reply_text(f'Deposit request #{did} admin approval के लिए भेज दी गई है।')
 for a in all('SELECT user_id FROM admins'):
  try:await context.bot.send_photo(a['user_id'],update.message.photo[-1].file_id,caption=f'💳 NEW DEPOSIT REQUEST\\nID: {did}\\nUser: {uid}\\nAmount: ₹{u["dep_amount"]}\\nUTR: {u["utr"]}',reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('✅ APPROVE',callback_data=f'approve:{did}'),InlineKeyboardButton('❌ REJECT',callback_data=f'reject:{did}')]]))
  except Exception:log.exception('admin notification failed')

def normalize_provider_status(raw):
    text=str(raw or '').strip().lower().replace('_',' ').replace('-',' ')
    if text in ('pending','queued','waiting','awaiting'):
        return 'PENDING'
    if text in ('in progress','processing','running'):
        return 'PROCESSING'
    if text in ('completed','complete','done'):
        return 'COMPLETED'
    if text in ('partial','partially completed'):
        return 'PARTIAL'
    if text in ('canceled','cancelled','failed','error'):
        return 'CANCELED' if text != 'failed' else 'FAILED'
    if text in ('refunded','refund'):
        return 'REFUNDED'
    return 'PROCESSING'


async def notify_order_status(bot, order, old_status, new_status):
    if old_status == new_status:
        return
    messages={
        'PENDING':f'🕐 आपका order #{order["id"]} provider पर PENDING है।',
        'PROCESSING':f'⚙️ आपका order #{order["id"]} अब PROCESSING में है।',
        'COMPLETED':f'✅ आपका order #{order["id"]} COMPLETED हो गया है।',
        'PARTIAL':f'⚠️ आपका order #{order["id"]} PARTIAL complete हुआ है।',
        'CANCELED':f'❌ आपका order #{order["id"]} provider ने CANCELED किया है।',
        'FAILED':f'❌ आपका order #{order["id"]} provider पर FAILED हुआ।',
        'REFUNDED':f'💸 आपका order #{order["id"]} provider पर REFUNDED हुआ।',
    }
    try:
        await bot.send_message(order['user_id'], messages.get(new_status,f'📦 आपका order #{order["id"]} status: {new_status}'))
    except Exception:
        log.exception('order status notification failed for %s',order['id'])


async def sync_provider_orders(context):
    rows=all("SELECT o.*,s.name,s.provider_id,s.provider_service_id FROM orders o JOIN services s ON s.id=o.service_id WHERE o.provider_order_id IS NOT NULL AND o.status IN ('PENDING','PROCESSING','PARTIAL') ORDER BY o.id LIMIT 100")
    for order in rows:
        try:
            provider=one('SELECT * FROM providers WHERE id=? AND active=1',(order['provider_id'],))
            if not provider:
                continue
            result=await GenericSMM(provider['api_url'],provider['api_key']).get_order_status(order['provider_order_id'])
            raw=result.get('status') if isinstance(result,dict) else result
            new_status=normalize_provider_status(raw)
            old_status=order['status']
            if new_status != old_status:
                run('UPDATE orders SET status=? WHERE id=? AND status=?',(new_status,order['id'],old_status))
                await notify_order_status(context.bot,order,old_status,new_status)
                if new_status in ('CANCELED','FAILED','REFUNDED') and not order['refund_issued']:
                    with connect() as c:
                        changed=c.execute("UPDATE orders SET refund_issued=1 WHERE id=? AND refund_issued=0",(order['id'],)).rowcount
                    if changed:
                        credit(order['user_id'],order['amount'],'REFUND',f'Provider {new_status} refund for order #{order["id"]}')
                        try:
                            await context.bot.send_message(order['user_id'],f'💰 ₹{order["amount"]:.2f} refund wallet में credit कर दिया गया है।')
                        except Exception:
                            log.exception('refund notification failed for %s',order['id'])
        except Exception:
            log.exception('provider status sync failed for order %s',order['id'])


async def approve_order(update,context,oid):
 q=update.callback_query
 with connect() as c:
  order=c.execute("SELECT o.*,s.name, s.provider_id, s.provider_service_id, s.active AS service_active FROM orders o JOIN services s ON s.id=o.service_id WHERE o.id=? AND o.status='PENDING_APPROVAL'",(oid,)).fetchone()
  if not order:return await q.answer('Order already processed or not found',show_alert=True)
  claimed=c.execute("UPDATE orders SET status='APPROVED' WHERE id=? AND status='PENDING_APPROVAL'",(oid,)).rowcount
  if claimed != 1:return await q.answer('Order already processed or not found',show_alert=True)
 try:
  provider=one('SELECT * FROM providers WHERE id=? AND active=1',(order['provider_id'],))
  if not provider:raise RuntimeError('Active provider unavailable')
  smm=GenericSMM(provider['api_url'],provider['api_key'])
  # Provider-side balance is checked before placing the real order. The provider
  # normally deducts the order cost when the `add` call succeeds.
  balance_result=await smm.get_balance()
  balance_value=balance_result.get('balance') if isinstance(balance_result,dict) else balance_result
  try: provider_balance=float(balance_value)
  except (TypeError,ValueError): provider_balance=None
  if provider_balance is not None and provider_balance < 0:
   raise RuntimeError('Provider balance is invalid')
  result=await smm.create_order(order['provider_service_id'],order['target'],order['quantity'])
  provider_id=str(result.get('order') if isinstance(result,dict) else result)
  if not provider_id or provider_id.lower() in ('none','null'):
   raise RuntimeError(f'Provider did not return an order ID: {result}')
  # The order has been accepted by the provider; its first real status is synced
  # from the provider instead of assuming PROCESSING.
  initial='PENDING'
  if isinstance(result,dict) and result.get('status'):
   initial=normalize_provider_status(result.get('status'))
  run("UPDATE orders SET provider_order_id=?,status=? WHERE id=? AND status='APPROVED'",(provider_id,initial,oid))
  caption=f'✅ Order #{oid} confirmed and sent to provider.\nProvider ID: {provider_id}\nProvider status: {initial}'
  if provider_balance is not None: caption += f'\nProvider balance before order: {provider_balance:.2f}'
  if q.message.photo: await q.edit_message_caption(caption=caption)
  else: await q.edit_message_text(caption)
  await context.bot.send_message(order['user_id'],f'✅ आपका order #{oid} admin ने confirm कर दिया है।\nProvider Order ID: {provider_id}\nStatus: {initial}')
 except Exception as exc:
  log.exception('approved order dispatch failed for order %s',oid)
  run("UPDATE orders SET status='FAILED' WHERE id=? AND status='APPROVED'",(oid,))
  credit(order['user_id'],order['amount'],'REFUND',f'Provider failed after admin approval for order #{oid}')
  if q.message.photo: await q.edit_message_caption(caption=f'❌ Order #{oid} failed; amount refunded.')
  else: await q.edit_message_text(f'❌ Order #{oid} failed; amount refunded.')
  await context.bot.send_message(order['user_id'],f'❌ आपका order #{oid} provider को भेजा नहीं जा सका। ₹{order["amount"]:.2f} refund कर दिया गया है।')


async def pending_deposits(update,context):
 q=update.callback_query;rs=all("SELECT * FROM deposits WHERE status='PENDING' ORDER BY id DESC LIMIT 20");rows=[[InlineKeyboardButton(f"#{x['id']} ₹{x['amount']:.2f}",callback_data=f'approve:{x["id"]}') ] for x in rs];rows.append([InlineKeyboardButton('⬅️ BACK',callback_data='admin')]);await q.edit_message_text('Pending deposits:',reply_markup=InlineKeyboardMarkup(rows))
async def remove_admin_deposit_message(q, caption):
 # Delete the complete admin notification so both APPROVE and REJECT buttons disappear.
 # If Telegram cannot delete it, edit the message and explicitly remove its keyboard.
 try:
  if q.message:
   await q.message.delete()
   return
 except Exception:
  log.warning('could not delete admin deposit message; falling back to edit', exc_info=True)
 if q.message and q.message.photo:
  await q.edit_message_caption(caption=caption, reply_markup=None)
 else:
  await q.edit_message_text(caption, reply_markup=None)

async def deposit_callback(update, context):
 q=update.callback_query
 if not is_admin(q.from_user.id):
  await q.answer('केवल admin deposit process कर सकता है।', show_alert=True)
  return
 await q.answer()
 try:
  action, raw_id = str(q.data).split(':', 1)
  did=int(raw_id)
 except (ValueError, AttributeError):
  await q.edit_message_text('Invalid deposit action.', reply_markup=None)
  return
 if action == 'approve':
  return await approve(update, context, did)
 if action == 'reject':
  return await reject(update, context, did)
 await q.edit_message_text('Invalid deposit action.', reply_markup=None)

async def approve(update,context,did):
 q=update.callback_query
 try:
  with connect() as c:
   d=c.execute("SELECT * FROM deposits WHERE id=? AND status='PENDING'",(did,)).fetchone()
   if not d:
    await q.answer('यह deposit पहले ही process हो चुका है या मिला नहीं।',show_alert=True)
    return
   c.execute("UPDATE deposits SET status='APPROVED' WHERE id=? AND status='PENDING'",(did,))
  credit(d['user_id'],d['amount'],'DEPOSIT',f'Deposit #{did} approved')
  referral_reward=0.0; referrer_id=None
  ref=one('SELECT id,referrer_id,qualified FROM referrals WHERE referred_id=?',(d['user_id'],))
  if ref and not ref['qualified']:
   try: configured=float(setting('referral_reward','0') or 0)
   except (TypeError,ValueError): configured=0.0
   if configured > 0:
    with connect() as c:
     changed=c.execute('UPDATE referrals SET qualified=1,reward=? WHERE id=? AND qualified=0',(configured,ref['id'])).rowcount
    if changed:
     referral_reward=configured; referrer_id=ref['referrer_id']
  if referrer_id and referral_reward > 0:
   credit(referrer_id,referral_reward,'REFERRAL',f'Successful referral reward for user {d["user_id"]}')
   try: await context.bot.send_message(referrer_id,f'🎉 Referral reward मिला! User {d["user_id"]} का first deposit approved हुआ और ₹{referral_reward:.2f} आपके wallet में credit किया गया।')
   except Exception: log.exception('referral reward notification failed for %s',referrer_id)
  await remove_admin_deposit_message(q, f'✅ Deposit #{did} APPROVED | ₹{d["amount"]:.2f} credited')
  await context.bot.send_message(d['user_id'],f'✅ Deposit #{did} approved. ₹{d["amount"]:.2f} credited.')
 except Exception:
  log.exception('deposit approval failed for %s',did)
  await q.answer('Approve करते समय error आया। Logs जाँचें।',show_alert=True)

async def reject(update,context,did):
 q=update.callback_query
 try:
  with connect() as c:
   d=c.execute("SELECT * FROM deposits WHERE id=? AND status='PENDING'",(did,)).fetchone()
   if not d:
    await q.answer('यह deposit पहले ही process हो चुका है या मिला नहीं।',show_alert=True)
    return
   c.execute("UPDATE deposits SET status='REJECTED' WHERE id=? AND status='PENDING'",(did,))
  await remove_admin_deposit_message(q, f'❌ Deposit #{did} REJECTED')
  await context.bot.send_message(d['user_id'],f'❌ Deposit #{did} rejected.')
 except Exception:
  log.exception('deposit rejection failed for %s',did)
  await q.answer('Reject करते समय error आया। Logs जाँचें।',show_alert=True)
async def checkchannels(update,context):
 if not await admin_ok(update,context):return await update.message.reply_text('पहले /admin से password verify करें।')
 lines=[]
 for c in all('SELECT * FROM channels WHERE active=1'):
  try:
   channel_ref=normalize_channel_ref(c['channel_id'])
   if not channel_ref:
    lines.append(f"❌ {c['name']} | invalid channel ID/username")
    continue
   chat=await context.bot.get_chat(channel_ref)
   bot_member=await context.bot.get_chat_member(chat.id, (await context.bot.get_me()).id)
   lines.append(f"✅ {c['name']} | ID: {chat.id} | bot: {bot_member.status}")
  except Exception as exc:
   lines.append(f"❌ {c['name']} | configured: {c['channel_id']} | {str(exc)[:120]}")
 await update.message.reply_text('📢 CHANNEL CHECK\\n'+'\\n'.join(lines) if lines else 'कोई active channel configured नहीं है।')
async def resolve_user_id(context,raw):
 raw=raw.strip()
 try:return int(raw)
 except ValueError:
  if not raw.startswith('@'):return None
  try:return (await context.bot.get_chat(raw)).id
  except Exception:return None

async def add_scanner_target(update,context,raw):
 if len(all("SELECT * FROM admins WHERE role='SCANNER_ADMIN'"))>=4:
  return await update.message.reply_text('Maximum 4 Scanner Admins allowed.')
 target_id=await resolve_user_id(context,raw)
 if not target_id:return await update.message.reply_text('सही numeric Telegram USER ID या @username भेजें।')
 if is_admin(target_id):return await update.message.reply_text('यह user पहले से admin/scanner admin है।')
 run("INSERT INTO admins(user_id,role) VALUES(?, 'SCANNER_ADMIN')",(target_id,))
 return await update.message.reply_text(f'✅ Scanner Admin added: {target_id}\\nअब वह /admin से password verify करके payment QR/deposits manage कर सकता है।',reply_markup=admin_panel())

async def remove_admin_target(update,context,raw):
 target_id=await resolve_user_id(context,raw)
 if not target_id:return await update.message.reply_text('सही numeric Telegram USER ID या @username भेजें।')
 if target_id==SUPER_ADMIN_ID:return await update.message.reply_text('SUPER_ADMIN को remove नहीं किया जा सकता।')
 deleted=run("DELETE FROM admins WHERE user_id=? AND role='ADMIN'",(target_id,))
 return await update.message.reply_text('✅ Admin removed.' if deleted else '❌ ADMIN नहीं मिला।',reply_markup=admin_panel())

async def remove_scanner_target(update,context,raw):
 target_id=await resolve_user_id(context,raw)
 if not target_id:return await update.message.reply_text('सही numeric Telegram USER ID या @username भेजें।')
 deleted=run("DELETE FROM admins WHERE user_id=? AND role='SCANNER_ADMIN'",(target_id,))
 return await update.message.reply_text('✅ Scanner Admin removed.' if deleted else '❌ Scanner Admin नहीं मिला।',reply_markup=admin_panel())

async def add_admin_target(update,context,raw):
 if len(all("SELECT * FROM admins WHERE role='ADMIN'"))>=4:return await update.message.reply_text('Maximum 4 additional admins allowed.')
 target_id=await resolve_user_id(context,raw)
 if not target_id:return await update.message.reply_text('सही numeric Telegram USER ID या @username भेजें।')
 if is_admin(target_id):return await update.message.reply_text('यह user पहले से admin/scanner admin है।')
 run("INSERT INTO admins(user_id,role) VALUES(?, 'ADMIN')",(target_id,))
 return await update.message.reply_text(f'✅ Admin added: {target_id}\nअब वह /admin चलाकर password verify कर सकता है।',reply_markup=admin_panel())

async def admin(update,context):
 user(update.effective_user)
 if not is_admin(update.effective_user.id): return await update.message.reply_text("Unauthorized")
 if context.args and is_super(update.effective_user.id):
  return await add_admin_target(update,context,context.args[0])
 context.user_data["admin_password_pending"] = True
 await update.message.reply_text("🔐 Admin password भेजें।\\nSuper admin सीधे ID भी भेज सकता है: /admin USER_ID")
async def addadmin(update,context):
 if not is_super(update.effective_user.id):return await update.message.reply_text('केवल SUPER_ADMIN admin जोड़ सकता है।')
 if len(context.args)!=1:return await update.message.reply_text('Usage: /addadmin USER_ID या @username')
 return await add_admin_target(update,context,context.args[0])
async def removeadmin(update,context):
 if is_super(update.effective_user.id) and len(context.args)==1:
  return await remove_admin_target(update,context,context.args[0])
 return await update.message.reply_text('केवल SUPER_ADMIN उपयोग कर सकता है: /removeadmin USER_ID')

async def addscanneradmin(update,context):
 if not is_super(update.effective_user.id):return await update.message.reply_text('केवल SUPER_ADMIN Scanner Admin जोड़ सकता है।')
 if len(context.args)!=1:return await update.message.reply_text('Usage: /addscanneradmin USER_ID या @username')
 return await add_scanner_target(update,context,context.args[0])

async def removescanneradmin(update,context):
 if not is_super(update.effective_user.id):return await update.message.reply_text('केवल SUPER_ADMIN Scanner Admin हटा सकता है।')
 if len(context.args)!=1:return await update.message.reply_text('Usage: /removescanneradmin USER_ID या @username')
 return await remove_scanner_target(update,context,context.args[0])

async def admin_ok(update, context):
 return bool(is_admin(update.effective_user.id) and context.user_data.get('admin_authenticated'))
async def settings_cmd(update,context):
 if not await admin_ok(update,context): return await update.message.reply_text('Unauthorized')
 raw=' '.join(context.args); parts=[x.strip() for x in raw.split('|',1)]
 if len(parts)!=2:return await update.message.reply_text('Format: /set key | value')
 run('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',parts);await update.message.reply_text('✅ Setting saved.')
async def qr_cmd(update,context):
 if not (await admin_ok(update,context) and is_scanner_admin(update.effective_user.id)):return await update.message.reply_text('Unauthorized')
 if not update.message.photo:return
 f=update.message.photo[-1].file_id;run("INSERT INTO settings(key,value) VALUES('qr_file_id',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(f,));run("INSERT INTO settings(key,value) VALUES('qr_enabled','1') ON CONFLICT(key) DO UPDATE SET value='1'");await update.message.reply_text('✅ QR saved and enabled.')
async def qr_off(update,context):
 if await admin_ok(update,context) and is_scanner_admin(update.effective_user.id):
  run("INSERT INTO settings(key,value) VALUES('qr_enabled','0') ON CONFLICT(key) DO UPDATE SET value='0'")
  await update.message.reply_text('⏸ QR disabled. नया QR हटाया नहीं गया है; SCANNER QR → SET / REPLACE से फिर enable कर सकते हैं।')
 else:
  await update.message.reply_text('Unauthorized')

async def quickredeem(update,context):
 if not await admin_ok(update,context):return await update.message.reply_text('पहले /admin से password verify करें।')
 if len(context.args)!=4:return await update.message.reply_text('Usage: /quickredeem CODE REWARD USERS EXPIRY_HOURS')
 code=context.args[0].upper().replace(' ','')
 try:reward=amount(context.args[1]); limit=int(context.args[2]); hours=int(context.args[3])
 except ValueError:reward=None;limit=0;hours=0
 if not code.isalnum() or not reward or limit<1 or hours<1:return await update.message.reply_text('Example: /quickredeem WELCOME50 50 100 24')
 expiry=(datetime.now(timezone.utc)+timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S UTC')
 try:
  run('INSERT INTO redeem_codes(code,reward,usage_limit,expires_at) VALUES(?,?,?,?)',(code,reward,limit,expiry));return await update.message.reply_text(f'✅ Redeem code created: {code}\\nReward ₹{reward:.2f} | Users {limit} | Expiry {expiry}')
 except sqlite3.IntegrityError:return await update.message.reply_text('❌ यह code पहले से मौजूद है।')
async def channelgate(update,context):
 if not await admin_ok(update,context):return await update.message.reply_text('पहले /admin से password verify करें।')
 if len(context.args)!=1 or context.args[0].lower() not in ('on','off'):return await update.message.reply_text('Usage: /channelgate on या /channelgate off')
 value='1' if context.args[0].lower()=='on' else '0'
 run('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('channel_gate_enabled',value))
 await update.message.reply_text('✅ Channel gate '+('enabled.' if value=='1' else 'disabled. Users सीधे dashboard खोल सकेंगे।'))
async def aitest(update,context):
 if not await admin_ok(update,context):return await update.message.reply_text('पहले /admin से password verify करें।')
 try:
  answer=await ai_complete('Reply with exactly: AI connection is working.')
  return await update.message.reply_text('✅ AI connection working.\\n'+answer)
 except Exception as exc:
  log.warning('AI test failed: %s',exc)
  return await update.message.reply_text('❌ AI connection failed. AI URL, key और model जाँचें।')
async def addredeem(update,context):
 if not await admin_ok(update,context):return await update.message.reply_text('पहले /admin से password verify करें।')
 p=[x.strip() for x in ' '.join(context.args).split('|')]
 if len(p)!=4:return await update.message.reply_text('Format: /addredeem CODE|REWARD|USAGE_LIMIT|EXPIRY_YYYY-MM-DD')
 code=p[0].upper().replace(' ','')
 try:
  reward=amount(p[1]); limit=int(p[2]); expiry=p[3]
  if not code.isalnum() or len(code)<3 or not reward or limit<1: raise ValueError
  datetime.strptime(expiry,'%Y-%m-%d')
  run('INSERT INTO redeem_codes(code,reward,usage_limit,expires_at) VALUES(?,?,?,?)',(code,reward,limit,expiry+' 23:59:59 UTC'))
  await update.message.reply_text(f'✅ Redeem code created: {code}\nReward: ₹{reward:.2f} | Users: {limit} | Expiry: {expiry}')
 except sqlite3.IntegrityError:
  await update.message.reply_text('❌ यह code पहले से मौजूद है।')
 except (ValueError,TypeError):
  await update.message.reply_text('Invalid data. उदाहरण: /addredeem WELCOME50|50|100|2026-12-31')
 except Exception:
  log.exception('Redeem code creation failed')
  await update.message.reply_text('❌ Code create नहीं हो सका। Database/log जाँचें।')
async def addpromo(update,context):
 if not await admin_ok(update,context):return await update.message.reply_text('Unauthorized')
 p=[x.strip() for x in ' '.join(context.args).split('|')]
 if len(p)!=6:return await update.message.reply_text('Format: /addpromo CODE|percent/fixed|VALUE|MIN_ORDER|MAX_DISCOUNT|EXPIRY')
 try:run('INSERT INTO promo_codes(code,kind,value,min_order,max_discount,expires_at) VALUES(?,?,?,?,?,?)',(p[0].upper(),p[1],float(p[2]),float(p[3]),float(p[4]) if p[4] else None,p[5]));await update.message.reply_text('✅ Promo code created.')
 except Exception:await update.message.reply_text('Invalid or duplicate promo.')
async def addbonus(update,context):
 if not await admin_ok(update,context):return await update.message.reply_text('Unauthorized')
 p=[x.strip() for x in ' '.join(context.args).split('|')]
 if len(p)!=2:return await update.message.reply_text('Format: /addbonus welcome/daily/deposit/campaign|amount')
 run('INSERT INTO bonuses(key,value,active) VALUES(?,?,1) ON CONFLICT(key) DO UPDATE SET value=excluded.value,active=1',p);await update.message.reply_text('✅ Bonus configured.')
async def blockuser(update,context):
 if not await admin_ok(update,context) or len(context.args)!=1:return await update.message.reply_text('Usage: /block USER_ID')
 run('UPDATE users SET blocked=1 WHERE id=?',(int(context.args[0]),));await update.message.reply_text('User blocked.')
async def unblockuser(update,context):
 if not await admin_ok(update,context) or len(context.args)!=1:return await update.message.reply_text('Usage: /unblock USER_ID')
 run('UPDATE users SET blocked=0 WHERE id=?',(int(context.args[0]),));await update.message.reply_text('User unblocked.')
async def adjustbalance(update,context):
 if not await admin_ok(update,context) or len(context.args)<2:return await update.message.reply_text('Usage: /adjustbalance USER_ID AMOUNT | reason')
 try:
  uid=int(context.args[0]);a=float(context.args[1]);note=' '.join(context.args[2:]) or 'Admin adjustment';b=credit(uid,a,'ADMIN_ADJUSTMENT',note);run('INSERT INTO audit_logs(admin_id,action,details) VALUES(?,?,?)',(update.effective_user.id,'balance_adjust',f'{uid}:{a}:{note}'));await update.message.reply_text(f'Balance updated: ₹{b:.2f}')
 except Exception:await update.message.reply_text('Invalid amount or user.')
async def serverlist(update,context):
 if not await admin_ok(update,context):return await update.message.reply_text('Unauthorized')
 rows=all('SELECT id,name,api_url,active,priority FROM providers ORDER BY priority');await update.message.reply_text('\n'.join(f"#{x['id']} {x['name']} {'ON' if x['active'] else 'OFF'} {x['api_url']}" for x in rows) or 'No providers')
async def disableserver(update,context):
 if not await admin_ok(update,context) or len(context.args)!=1:return await update.message.reply_text('Usage: /disableserver ID')
 run('UPDATE providers SET active=0 WHERE id=?',(int(context.args[0]),));await update.message.reply_text('Server disabled.')
async def servicelist(update,context):
 if not await admin_ok(update,context):return await update.message.reply_text('Unauthorized')
 rows=all('SELECT id,name,category,selling_price,active FROM services ORDER BY id');await update.message.reply_text('\n'.join(f"#{x['id']} {x['name']} {x['category']} ₹{x['selling_price']}/1k {'ON' if x['active'] else 'OFF'}" for x in rows) or 'No services')
async def disableservice(update,context):
 if not await admin_ok(update,context) or len(context.args)!=1:return await update.message.reply_text('Usage: /disableservice ID')
 run('UPDATE services SET active=0 WHERE id=?',(int(context.args[0]),));await update.message.reply_text('Service disabled.')
async def error(update,context):log.exception('update error',exc_info=context.error)
async def wallet_cmd(update,context):
 user(update.effective_user); await update.message.reply_text(f"💰 WALLET\nAvailable Balance: ₹{wallet_balance(update.effective_user.id):.2f}",reply_markup=dashboard())
async def feature_cmd(update,context):
 user(update.effective_user); await update.message.reply_text('यह सुविधा Dashboard के buttons से खोलें।',reply_markup=dashboard())
async def help_cmd(update,context):
 await update.message.reply_text('/start /menu /balance /services /orders /track /profile /deposit /refer /redeem /promo /bonus /stats /support\nAdmin: /admin\nSuper admin: /addadmin /removeadmin /addscanneradmin /removescanneradmin')
def seed_code_channels():
    """Ensure configured default channels exist without overwriting admin-managed rows."""
    for ch in CODE_CHANNELS:
        try:
            name=str(ch["name"]).strip(); channel_id=str(ch["channel_id"]).strip(); invite_url=str(ch["invite_url"]).strip()
            if not name or not channel_id or not invite_url: continue
            existing=one('SELECT id FROM channels WHERE channel_id=? OR name=?',(channel_id,name))
            if existing:
                # Repair an old row whose channel username/ID was changed, while preserving active state.
                run('UPDATE channels SET name=?,channel_id=?,invite_url=? WHERE id=?',(name,channel_id,invite_url,existing['id']))
            else:
                run('INSERT INTO channels(name,channel_id,invite_url,active) VALUES(?,?,?,1)',(name,channel_id,invite_url))
        except Exception as e:
            log.warning('Could not seed/repair code channel %s: %s',ch,e)
    run("INSERT INTO settings(key,value) VALUES('code_channels_seeded','1') ON CONFLICT(key) DO UPDATE SET value='1'")

def main():
 if not BOT_TOKEN:raise SystemExit('BOT_TOKEN missing in .env')
 init_db();migrate_order_columns();seed_code_channels();asyncio.set_event_loop(asyncio.new_event_loop());app=Application.builder().token(BOT_TOKEN).build();app.job_queue.run_repeating(sync_provider_orders, interval=60, first=10);app.add_handler(CommandHandler('start',start));app.add_handler(CommandHandler('menu',menu));app.add_handler(CommandHandler('admin',admin));app.add_handler(CommandHandler('checkchannels',checkchannels));app.add_handler(CommandHandler('channelgate',channelgate));app.add_handler(CommandHandler('aitest',aitest));app.add_handler(CommandHandler('quickredeem',quickredeem));app.add_handler(CommandHandler('addadmin',addadmin));app.add_handler(CommandHandler('removeadmin',removeadmin));app.add_handler(CommandHandler('addscanneradmin',addscanneradmin));app.add_handler(CommandHandler('removescanneradmin',removescanneradmin));app.add_handler(CommandHandler('balance',wallet_cmd));app.add_handler(CommandHandler('services',feature_cmd));app.add_handler(CommandHandler('orders',feature_cmd));app.add_handler(CommandHandler('track',feature_cmd));app.add_handler(CommandHandler('profile',feature_cmd));app.add_handler(CommandHandler('deposit',feature_cmd));app.add_handler(CommandHandler('refer',feature_cmd));app.add_handler(CommandHandler('redeem',feature_cmd));app.add_handler(CommandHandler('promo',feature_cmd));app.add_handler(CommandHandler('bonus',feature_cmd));app.add_handler(CommandHandler('stats',feature_cmd));app.add_handler(CommandHandler('support',feature_cmd));app.add_handler(CommandHandler('help',help_cmd));app.add_handler(CommandHandler('set',settings_cmd));app.add_handler(CommandHandler('qr',qr_cmd));app.add_handler(CommandHandler('qr_off',qr_off));app.add_handler(CommandHandler('addredeem',addredeem));app.add_handler(CommandHandler('addpromo',addpromo));app.add_handler(CommandHandler('addbonus',addbonus));app.add_handler(CommandHandler('block',blockuser));app.add_handler(CommandHandler('unblock',unblockuser));app.add_handler(CommandHandler('adjustbalance',adjustbalance));app.add_handler(CommandHandler('servers',serverlist));app.add_handler(CommandHandler('disableserver',disableserver));app.add_handler(CommandHandler('servicelist',servicelist));app.add_handler(CommandHandler('disableservice',disableservice));app.add_handler(CallbackQueryHandler(deposit_callback, pattern=r'^(approve|reject):[0-9]+$'))
 app.add_handler(CallbackQueryHandler(cb));app.add_handler(MessageHandler(filters.PHOTO,photo));app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,text));app.add_error_handler(error);app.run_polling(allowed_updates=Update.ALL_TYPES)
if __name__=='__main__':main()


# Password is configurable through ADMIN_PASSWORD; default is the requested value.

