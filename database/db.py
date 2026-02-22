import aiosqlite
import logging

logger = logging.getLogger(__name__)
DB_PATH = "taxi_bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS drivers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                age INTEGER,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                car_number TEXT,
                phone_number TEXT,
                car_model TEXT,
                car_color TEXT,
                status TEXT DEFAULT 'offline',
                balance INTEGER DEFAULT 0,
                lang TEXT DEFAULT 'uz'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                telegram_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                phone_number TEXT,
                lang TEXT DEFAULT 'uz'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                count_of_people INTEGER DEFAULT 1,
                driver_id INTEGER,
                from_location TEXT NOT NULL,
                to_location TEXT NOT NULL,
                from_lat REAL,
                from_lon REAL,
                to_lat REAL,
                to_lon REAL,
                status TEXT DEFAULT 'pending',
                rejected_driver_ids TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id),
                FOREIGN KEY (driver_id) REFERENCES drivers(id)
            )
        """)
        # Migrate
        migrate_stmts = [
            "ALTER TABLE clients ADD COLUMN phone_number TEXT",
            "ALTER TABLE clients ADD COLUMN username TEXT",
            "ALTER TABLE drivers ADD COLUMN username TEXT",
            "ALTER TABLE orders ADD COLUMN from_lat REAL",
            "ALTER TABLE orders ADD COLUMN from_lon REAL",
            "ALTER TABLE orders ADD COLUMN to_lat REAL",
            "ALTER TABLE orders ADD COLUMN to_lon REAL",
            "ALTER TABLE orders ADD COLUMN rejected_driver_ids TEXT DEFAULT ''",
            "ALTER TABLE orders ADD COLUMN current_driver_idx INTEGER DEFAULT 0",
        ]
        for stmt in migrate_stmts:
            try:
                await db.execute(stmt)
                await db.commit()
            except Exception:
                pass

        # Mavjud orderlarda rejected_driver_ids NULL bo'lsa bo'sh string qilamiz
        try:
            await db.execute(
                "UPDATE orders SET rejected_driver_ids='' WHERE rejected_driver_ids IS NULL"
            )
            await db.commit()
        except Exception:
            pass


# ─── CLIENT ────────────────────────────────────────────────────────────────────

async def get_client(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM clients WHERE telegram_id=?", (telegram_id,)) as c:
            return await c.fetchone()


async def get_client_by_id(client_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM clients WHERE id=?", (client_id,)) as c:
            return await c.fetchone()


async def create_client(full_name, telegram_id, phone_number, lang="uz", username=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO clients (full_name,telegram_id,phone_number,lang,username) VALUES(?,?,?,?,?)",
            (full_name, telegram_id, phone_number, lang, username)
        )
        await db.commit()


async def update_client(telegram_id: int, **kwargs):
    if not kwargs: return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [telegram_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE clients SET {fields} WHERE telegram_id=?", values)
        await db.commit()


async def update_client_lang(telegram_id: int, lang: str):
    await update_client(telegram_id, lang=lang)


# ─── DRIVER ────────────────────────────────────────────────────────────────────

async def get_driver(telegram_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM drivers WHERE telegram_id=?", (telegram_id,)) as c:
            return await c.fetchone()


async def get_driver_by_id(driver_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM drivers WHERE id=?", (driver_id,)) as c:
            return await c.fetchone()


async def create_driver(full_name, age, telegram_id, car_number, phone_number,
                        car_model, car_color, lang="uz", username=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT OR IGNORE INTO drivers
               (full_name,age,telegram_id,car_number,phone_number,car_model,car_color,lang,username)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (full_name, age, telegram_id, car_number, phone_number, car_model, car_color, lang, username)
        )
        await db.commit()


async def update_driver(telegram_id: int, **kwargs):
    if not kwargs: return
    fields = ", ".join(f"{k}=?" for k in kwargs)
    values = list(kwargs.values()) + [telegram_id]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE drivers SET {fields} WHERE telegram_id=?", values)
        await db.commit()


async def update_driver_status(telegram_id: int, status: str):
    await update_driver(telegram_id, status=status)


async def update_driver_lang(telegram_id: int, lang: str):
    await update_driver(telegram_id, lang=lang)


async def get_online_drivers_sorted(exclude_ids: list = None):
    """
    Online driverlarni balance ASC tartibda qaytaradi.
    exclude_ids — allaqachon rad etgan driverlar ID lari (DB id, telegram_id emas).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM drivers WHERE status='online' ORDER BY balance ASC"
        ) as c:
            all_drivers = await c.fetchall()

    if not exclude_ids:
        return list(all_drivers)

    # Rad etgan driverlarni chiqarib tashlaymiz
    return [d for d in all_drivers if d["id"] not in exclude_ids]


# ─── ORDER ─────────────────────────────────────────────────────────────────────

async def create_order(client_id, count, from_location, to_location,
                       from_lat=None, from_lon=None, to_lat=None, to_lon=None):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """INSERT INTO orders
               (client_id,count_of_people,from_location,to_location,
                from_lat,from_lon,to_lat,to_lon,rejected_driver_ids)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (client_id, count, from_location, to_location,
             from_lat, from_lon, to_lat, to_lon, "")
        )
        await db.commit()
        return cur.lastrowid


async def get_order(order_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM orders WHERE id=?", (order_id,)) as c:
            return await c.fetchone()


async def update_order_status(order_id: int, status: str, driver_id: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if driver_id:
            await db.execute(
                "UPDATE orders SET status=?,driver_id=? WHERE id=?",
                (status, driver_id, order_id)
            )
        else:
            await db.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        await db.commit()


async def add_rejected_driver(order_id: int, driver_db_id: int):
    """
    Rad etgan driver ID sini orders.rejected_driver_ids ga qo'shadi.
    Format: '1,5,12' — vergul bilan ajratilgan DB id lar.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT rejected_driver_ids FROM orders WHERE id=?", (order_id,)) as c:
            row = await c.fetchone()
        if not row:
            return
        existing = row["rejected_driver_ids"] or ""
        ids = [x for x in existing.split(",") if x.strip()]
        if str(driver_db_id) not in ids:
            ids.append(str(driver_db_id))
        await db.execute(
            "UPDATE orders SET rejected_driver_ids=? WHERE id=?",
            (",".join(ids), order_id)
        )
        await db.commit()


def parse_rejected_ids(rejected_str: str) -> list:
    """'1,5,12' -> [1, 5, 12]"""
    if not rejected_str:
        return []
    try:
        return [int(x) for x in rejected_str.split(",") if x.strip()]
    except Exception:
        return []


async def increment_driver_balance(driver_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE drivers SET balance=balance+1 WHERE id=?", (driver_id,))
        await db.commit()


async def get_client_active_order(client_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """SELECT * FROM orders WHERE client_id=?
               AND status IN ('pending','accepted')
               ORDER BY id DESC LIMIT 1""",
            (client_id,)
        ) as c:
            return await c.fetchone()
