import json
import os
import datetime
import uuid  # Unique IDs banane ke liye (ObjectId ka substitute)

# Database Folder Setup (Jahan saari JSON files save hongi)
DB_FOLDER = "json_db"
if not os.path.exists(DB_FOLDER):
    os.makedirs(DB_FOLDER)


# ==================================================================
# 🔌 JSON DATABASE CONNECTION (Fake MongoDB Wrapper)
# ==================================================================

# Helper functions to Read/Write JSON files
def get_db(file_name):
    path = f"{DB_FOLDER}/{file_name}.json"
    if not os.path.exists(path):
        with open(path, "w") as f: json.dump({}, f)
    with open(path, "r") as f:
        return json.load(f)

def save_db(file_name, data):
    path = f"{DB_FOLDER}/{file_name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=4, default=str)


# ==================================================================
# 🚀 ASYNC CURSOR: MongoDB cursor behavior for JSON
# ==================================================================
class AsyncCursor:
    def __init__(self, items):
        self.items = items

    def sort(self, key, direction=-1):
        # Python ki list ko sort karne ka logic
        self.items.sort(key=lambda x: x.get(key), reverse=(direction == -1))
        return self # Return self taaki chaining chalti rahe

    async def to_list(self, length=None):
        if length:
            return self.items[:length]
        return self.items

    async def __anext__(self):
        if self.index < len(self.items):
            item = self.items[self.index]
            self.index += 1
            return item
        raise StopAsyncIteration

    async def to_list(self, length=None):
        return self.items[:length] if length else self.items
    

# ==================================================================
# 📂 JSON COLLECTION: Main Database Logic
# ==================================================================
class JsonCollection:
    def __init__(self, name):
        self.name = name

    def find(self, query=None):
        """Saare documents dhoondne ke liye (cursor return karega)"""
        data = get_db(self.name) or {}
        results = []
        
        if not query:
            results = list(data.values())
        else:
            for item in data.values():
                match = True
                for key, value in query.items():
                    if item.get(key) != value:
                        match = False
                        break
                if match:
                    results.append(item)
        
        return AsyncCursor(results)

    async def find_one(self, query):
        """Ek single document dhoondne ke liye"""
        data = get_db(self.name) or {}
        
        if "_id" in query:
            target_id = str(query["_id"])
            return data.get(target_id)
            
        for item in data.values():
            match = True
            for key, value in query.items():
                if item.get(key) != value:
                    match = False
                    break
            if match:
                return item
        return None
    async def delete_many(self, query=None):
        """Saare data ya query match hone wale data ko delete karne ke liye"""
        # 1. Pehle puraana data load karein
        data = get_db(self.name) or {}
        
        if not query or query == {}:
            # 2. Agar query khali hai ({}), toh poora data uda do
            data = {}
        else:
            # 3. Agar query di hai, toh match hone wale items ko filter out karein
            # Hum ek naya dict banayenge jisme match hone wale items NAHI honge
            new_data = {}
            for key, item in data.items():
                match = True
                for k, v in query.items():
                    if item.get(k) != v:
                        match = False
                        break
                if not match: # Sirf unhe rakho jo match NAHI ho rahe
                    new_data[key] = item
            data = new_data
        
        # 4. Aapka apna save function use karein
        save_db(self.name, data) 
        return True

    async def update_one(self, filter_query, update_data, upsert=False):
        """MongoDB style update_one"""
        user_id = str(filter_query.get("_id"))
        data = get_db(self.name) or {}
        
        if user_id not in data:
            if upsert:
                data[user_id] = {"_id": int(user_id)}
            else:
                return False
                
        actual_data = update_data.get("$set", update_data)
        data[user_id].update(actual_data)
        save_db(self.name, data)
        return True

    async def update(self, filter_query, update_data):
        """Update alias"""
        return await self.update_one(filter_query, update_data)

    async def count_documents(self, query=None):
        """Total count nikalne ke liye"""
        data = get_db(self.name) or {}
        if not query:
            return len(data)
            
        count = 0
        for item in data.values():
            match = True
            for key, value in query.items():
                if item.get(key) != value:
                    match = False
                    break
            if match:
                count += 1
        return count




        # MongoDB ki tarah _id ya user_id se search karne ke liye
        search_id = str(query.get("_id") or query.get("user_id") or query.get("code", ""))
        return data.get(search_id)
    async def find_one(self, query):
        """MongoDB style find_one for JSON compatibility"""
        data = get_db(self.name)
        
        # Agar query mein _id hai toh direct return karo (Fastest)
        if "_id" in query:
            target_id = str(query["_id"])
            return data.get(target_id)
            
        # Warna poore data mein filter karo
        for item in data.values():
            match = True
            for key, value in query.items():
                if item.get(key) != value:
                    match = False
                    break
            if match:
                return item
        return None

    async def insert_one(self, document):
        data = get_db(self.name)
        # Agar _id nahi hai toh naya banao
        doc_id = str(document.get("_id") or document.get("user_id") or uuid.uuid4())
        document["_id"] = doc_id
        data[doc_id] = document
        save_db(self.name, data)
        # Mock result for .inserted_id
        return type('Result', (object,), {'inserted_id': doc_id})

    # Baaki updates hum functions ke andar handle karenge
    def aggregate(self, pipeline):
        # JSON mein aggregate nahi hota, iska workaround hum loop se karenge
        return self

# Collections (Ab ye MongoDB ki jagah JSON files use karenge)
col_users = JsonCollection("users")
col_stock = JsonCollection("stock")
col_orders = JsonCollection("orders")
col_payments = JsonCollection("payments")
col_fsub = JsonCollection("fsub")
col_settings = JsonCollection("settings")
col_coupons = JsonCollection("coupons")

# Plugins ke 'from database import db' error ko rokne ke liye
class MockDB:
    def __getitem__(self, name): return JsonCollection(name)
db = MockDB()

# ==================================================================
# 👤 1. USER MANAGEMENT
# ==================================================================

async def add_user(user_id, name):
    # JSON mein check karne ke liye:
    user = await col_users.find_one({"_id": user_id})
    if not user:
        # insert_one humne JsonCollection class mein define kiya hai
        await col_users.insert_one({
            "_id": str(user_id), # ID ko hamesha string rakho JSON ke liye
            "name": name,
            "balance": 0.0,
            "total_deposit": 0.0,
            "terms_accepted": False,
            "join_date": str(datetime.datetime.now()) # JSON datetime nahi samajhta, string do
        })

async def get_user(user_id):
    return await col_users.find_one({"_id": user_id})

async def update_balance(user_id, amount):
    """
    Updates user balance manually for JSON.
    """
    users = get_db("users") # Poori file read karo
    uid = str(user_id)
    
    if uid in users:
        # Current balance nikalo aur amount add karo
        current_balance = float(users[uid].get("balance", 0.0))
        users[uid]["balance"] = current_balance + amount
        
        # Agar deposit hai toh total_deposit bhi badhao
        if amount > 0:
            current_total = float(users[uid].get("total_deposit", 0.0))
            users[uid]["total_deposit"] = current_total + amount
            
        save_db("users", users) # File wapas save karo
        return True
    return False


# ==================================================================
# 📦 2. STOCK MANAGEMENT (JSON UNIFIED VIEW)
# ==================================================================

async def add_stock(category, items_list):
    if not items_list: return 0
    stock = get_db("stock")
    inserted_ids = []
    
    for item in items_list:
        # Unique ID generate karo har stock item ke liye
        sid = str(uuid.uuid4())
        item["_id"] = sid
        item["category"] = category 
        item["date_added"] = str(datetime.datetime.now())
        stock[sid] = item
        inserted_ids.append(sid)
    
    save_db("stock", stock)
    return len(inserted_ids)

async def get_unique_buckets(target_type=None):
    """
    Manual Grouping for JSON:
    Groups fresh stock by Country + Price + Year.
    """
    stock = get_db("stock")
    buckets = {} # Temporary dictionary to group items

    for sid, item in stock.items():
        # Sirf 'fresh' stock uthao
        if item.get("status") == "fresh":
            # Grouping Key banao (Country + Price + Year + Type)
            key = (item['country'], item['price'], item['year'], item.get('type', 'session'))
            
            if key not in buckets:
                buckets[key] = {
                    "_id": {
                        "country": item['country'],
                        "price": item['price'],
                        "year": item['year'],
                        "flag": item.get("flag", "🏳️"),
                        "type": item.get("type", "session")
                    },
                    "count": 0,
                    "sample_id": sid
                }
            buckets[key]["count"] += 1

    # Dictionary ko list mein badlo aur sort karo
    result = list(buckets.values())
    result.sort(key=lambda x: x["_id"]["country"])
    return result

async def get_stock_stats(target_type="accounts"):
    buckets = await get_unique_buckets(target_type)
    stats = []
    for b in buckets:
        stats.append({
            "_id": str(b["sample_id"]), 
            "country": b["_id"]["country"],
            "price": b["_id"]["price"],
            "year": b["_id"]["year"],
            "flag": b["_id"].get("flag", "🏳️"),
            "count": b["count"],
            "type": b["_id"].get("type", "session")
        })
    return stats

async def get_product_details(product_id):
    stock = get_db("stock")
    return stock.get(str(product_id))

async def get_stock_count(country, item_type, price, year):
    stock = get_db("stock")
    count = 0
    for item in stock.values():
        if (item.get("status") == "fresh" and 
            item.get("country") == country and 
            item.get("type") == item_type and 
            item.get("price") == price and 
            item.get("year") == year):
            count += 1
    return count


# ==================================================================
# 🛒 3. BUYING LOGIC (JSON Atomic Transactions)
# ==================================================================

async def buy_item_atomic(user_id, product_id, category):
    """
    JSON version of atomic purchase.
    """
    import datetime
    
    # Files load karo
    stock = get_db("stock")
    users = get_db("users")
    orders = get_db("orders")

    pid = str(product_id)
    uid = str(user_id)

    # 1. Fetch Item & User (Check if exist)
    item = stock.get(pid)
    if not item or item.get("status") != "fresh":
        return None

    user = users.get(uid)
    if not user:
        return None

    # 2. Check Balance
    price = float(item.get("price", 0))
    balance = float(user.get("balance", 0.0))

    if balance < price:
        return None

    # 3. Process Transaction (Simulated Atomic)
    # Deduct Balance
    users[uid]["balance"] = balance - price

    # Mark Stock as Sold
    item["status"] = "sold"
    item["sold_to"] = user_id
    item["sold_at"] = str(datetime.datetime.utcnow())

    # 4. Create Order Record
    order_id = str(uuid.uuid4())
    order_data = {
        "_id": order_id,
        "user_id": user_id,
        "item_id": pid,
        "data": item.get("data"),
        "phone": item.get("phone"),
        "price": price,
        "country": item.get("country", "Unknown"),
        "flag": item.get("flag", "🏳️"),
        "type": "session" if category == "sessions" else "account",
        "date": str(datetime.datetime.utcnow()),
        "otp": None
    }
    
    # 5. Save everything back to files
    orders[order_id] = order_data
    save_db("users", users)
    save_db("stock", stock)
    save_db("orders", orders)
    
    return order_data

async def get_order(order_id):
    """Required for OTP Checking."""
    orders = get_db("orders")
    return orders.get(str(order_id))

# ==================================================================
# 💰 4. PAYMENTS & DEPOSITS
# ==================================================================

async def get_deposit(utr):
    """
    Checks if UTR exists in JSON database.
    """
    payments = get_db("payments")
    # Loop chala kar har payment ka UTR check karo
    for payment_id, data in payments.items():
        if str(data.get("utr")) == str(utr):
            return data
    return None

async def create_deposit(user_id, amount, utr, method, status="pending"):
    """
    Creates a deposit log.
    Returns 'duplicate' if UTR exists, else 'created'.
    """
    # 1. Pehle check karo UTR duplicate toh nahi
    if await get_deposit(utr):
        return "duplicate"

    # 2. Nayi payment entry banao
    payments = get_db("payments")
    payment_id = str(uuid.uuid4()) # Unique ID for this payment entry
    
    payment_data = {
        "_id": payment_id,
        "user_id": user_id,
        "amount": amount,
        "utr": utr,
        "method": method,
        "status": status,
        "date": str(datetime.datetime.now()) # JSON ke liye string format
    }
    
    # 3. Save to file
    payments[payment_id] = payment_data
    save_db("payments", payments)
    
    return "created"


# ==================================================================
# 📦 2. STOCK MANAGEMENT (JSON 2-STEP MENU)
# ==================================================================

async def get_unique_countries():
    """
    Step 1: Returns unique countries for buttons.
    """
    stock = get_db("stock")
    countries = {}

    for item in stock.values():
        if item.get("status") == "fresh":
            c_name = item.get("country")
            if c_name not in countries:
                countries[c_name] = {
                    "_id": c_name,
                    "flag": item.get("flag", "🏳️")
                }
    
    # List mein convert karke sort karo
    result = list(countries.values())
    result.sort(key=lambda x: x["_id"])
    return result

async def get_buckets_by_country(country_name):
    """
    Step 2: Returns price/year buckets for specific country.
    """
    stock = get_db("stock")
    buckets = {}

    for sid, item in stock.items():
        if item.get("status") == "fresh" and item.get("country") == country_name:
            # Price, Year aur Type ke base par key banao
            key = (item['price'], item['year'], item.get('type', 'session'))
            
            if key not in buckets:
                buckets[key] = {
                    "sample_id": sid,
                    "price": item['price'],
                    "year": item['year'],
                    "flag": item.get("flag", "🏳️"),
                    "type": item.get("type", "session"),
                    "count": 0
                }
            buckets[key]["count"] += 1

    # Formatting for bot UI
    stats = []
    for b in buckets.values():
        stats.append({
            "_id": str(b["sample_id"]),
            "country": country_name,
            "price": b["price"],
            "year": b["year"],
            "flag": b["flag"],
            "count": b["count"],
            "type": b["type"]
        })
    
    stats.sort(key=lambda x: x["price"])
    return stats

# ==================================================================
# 📢 FSUB SETTINGS (JSON)
# ==================================================================

async def set_fsub(channel_id, link):
    settings = get_db("settings")
    settings["fsub"] = {
        "channel_id": channel_id,
        "link": link
    }
    save_db("settings", settings)

async def get_fsub():
    """Returns the fsub config."""
    settings = get_db("settings")
    return settings.get("fsub")


# ==================================================================
# 📢 MULTI-FSUB MANAGEMENT (JSON Unlimited Channels)
# ==================================================================

async def add_fsub(chat_id, invite_link, title):
    """Adds a new channel to the Force Sub list in JSON."""
    fsub = get_db("fsub")
    cid = str(chat_id)
    
    fsub[cid] = {
        "_id": chat_id,
        "link": invite_link,
        "title": title
    }
    
    save_db("fsub", fsub)
    return True

async def get_fsub_list():
    """Returns a list of all configured FSub channels from JSON."""
    fsub = get_db("fsub")
    # Dictionary ki values ko list mein convert karke return karo
    return list(fsub.values())

async def del_fsub(chat_id):
    """Removes a specific channel from FSub JSON."""
    fsub = get_db("fsub")
    cid = str(chat_id)
    
    if cid in fsub:
        del fsub[cid]
        save_db("fsub", fsub)
        return True
    return False

async def update_fsub(chat_id, invite_link=None, title="Channel"):
    """
    Adds or updates a channel. Matches admin.py logic.
    """
    if chat_id is None:
        return 
        
    fsub = get_db("fsub")
    cid = str(chat_id)
    
    # Purana data load karo ya naya banao
    data = fsub.get(cid, {"_id": chat_id})
    if invite_link:
        data["link"] = invite_link
    data["title"] = title
    
    fsub[cid] = data
    save_db("fsub", fsub)
    return True


# ==================================================================
# 🎟️ REDEEM / COUPON SYSTEM (JSON Style)
# ==================================================================

async def create_coupon(code: str, amount: int, limit: int):
    """Creates a new coupon code in JSON."""
    coupons = get_db("coupons")
    
    # Purana coupon code delete karo (Overwrite)
    coupons[code] = {
        "code": code,
        "amount": amount,
        "limit": int(limit),
        "used_count": 0,
        "used_by": [] # List of User IDs
    }
    
    save_db("coupons", coupons)
    return True

async def get_coupon(code: str):
    """Fetches coupon details from JSON."""
    coupons = get_db("coupons")
    return coupons.get(code)

async def redeem_coupon_db(user_id, code):
    """
    Attempts to redeem a coupon from JSON database.
    Returns: (Success: Bool, Message: Str, Amount: Int)
    """
    coupons = get_db("coupons")
    uid = str(user_id)
    
    if code not in coupons:
        return False, "❌ Invalid Code!", 0
        
    coupon = coupons[code]
    
    # 1. Check Limit
    if int(coupon["used_count"]) >= int(coupon["limit"]):
        return False, "❌ Coupon Limit Reached!", 0
        
    # 2. Check if already used by this user
    if uid in coupon.get("used_by", []):
        return False, "⚠️ You have already used this coupon!", 0
        
    # 3. Process Redemption (Manual Update)
    coupon["used_count"] += 1
    if "used_by" not in coupon: coupon["used_by"] = []
    coupon["used_by"].append(uid)
    
    # Save back to database
    coupons[code] = coupon
    save_db("coupons", coupons)
    
    return True, "✅ Coupon Redeemed!", int(coupon["amount"])


# ==================================================================
# 🤝 REFERRAL SYSTEM (JSON Milestone Based)
# ==================================================================

async def set_referrer(new_user_id, referrer_id):
    """
    Sets the referrer for a new user in JSON.
    """
    if str(new_user_id) == str(referrer_id):
        return False 
        
    users = get_db("users")
    uid = str(new_user_id)
    
    # Check if user exists and hasn't been referred yet
    if uid in users and not users[uid].get("referred_by"):
        users[uid]["referred_by"] = str(referrer_id)
        users[uid]["referral_paid"] = False # Bonus not paid yet
        
        save_db("users", users)
        return True
    return False

async def check_referral_milestone(user_id, current_deposit_amount):
    """
    Checks if User reached ₹1000 total deposit in JSON.
    """
    users = get_db("users")
    uid = str(user_id)
    
    if uid not in users or not users[uid].get("referred_by"):
        return None
        
    user_data = users[uid]
    
    if user_data.get("referral_paid"):
        return None # Already paid
        
    # Calculate Total Deposit
    prev_total = float(user_data.get("total_deposit", 0))
    # Note: current_deposit_amount yahan balance update se pehle ka ho sakta hai
    new_total = prev_total + float(current_deposit_amount)
    
    if new_total >= 1000:
        referrer_id = user_data["referred_by"]
        
        # 1. Give bonus to referrer
        await update_balance(referrer_id, 20)
        
        # 2. Mark as paid in the local data and save
        # Re-load users to get updated balance if necessary, but we can just update this user
        users = get_db("users") 
        users[uid]["referral_paid"] = True
        save_db("users", users)
        
        return referrer_id
        
    return None



# ==================================================================
# 🚧 MAINTENANCE & GLOBAL SETTINGS (JSON Style)
# ==================================================================

async def set_maintenance(status: bool):
    """Toggles Global Maintenance Mode in JSON."""
    settings = get_db("settings")
    
    # Check if main_config exists, else create it
    if "main_config" not in settings:
        settings["main_config"] = {}
        
    settings["main_config"]["maintenance"] = status
    save_db("settings", settings)
    return True

async def get_maintenance():
    """Checks if Maintenance Mode is ON or OFF."""
    settings = get_db("settings")
    config = settings.get("main_config", {})
    return config.get("maintenance", False)

async def update_usdt_rate(rate: float):
    """Updates the 1 USDT = INR rate in JSON."""
    settings = get_db("settings")
    
    if "main_config" not in settings:
        settings["main_config"] = {}
        
    settings["main_config"]["usdt_rate"] = float(rate)
    save_db("settings", settings)
    return True
