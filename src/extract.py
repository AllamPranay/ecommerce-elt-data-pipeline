"""
extract.py
----------
Extraction layer of the pipeline.

In a real production system this module would hit a REST API, a
transactional DB replica, or an event stream (Kafka). To keep this
project fully self-contained and reproducible for anyone who clones
the repo (no API keys, no external dependencies at extract time), it
generates a realistic synthetic e-commerce dataset: customers,
products, and daily order transactions with believable seasonality,
so it stands in for "day 1 vs day N incremental loads" the way a
real source system would.

Output lands in data/raw/ as CSVs, partitioned by extract date --
mirroring how raw data lands in an S3 / ADLS "bronze" landing zone
before being loaded into the warehouse.
"""
import csv
import random
import os
from datetime import date, datetime, timedelta

random.seed(42)  # reproducible runs -- important for demoing/debugging

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
               "Ananya", "Diya", "Ishita", "Kavya", "Myra", "Saanvi", "Priya",
               "Rohan", "Karan", "Neha", "Pooja", "Amit", "Sanya", "Liam",
               "Olivia", "Noah", "Emma", "Ava", "Sophia", "Mason", "Isabella"]
LAST_NAMES = ["Sharma", "Verma", "Patel", "Gupta", "Reddy", "Nair", "Iyer",
              "Singh", "Kumar", "Rao", "Mehta", "Joshi", "Kapoor", "Malhotra",
              "Smith", "Johnson", "Brown", "Davis", "Wilson", "Anderson"]
CITIES = [("Mumbai", "India"), ("Bengaluru", "India"), ("Delhi", "India"),
          ("Pune", "India"), ("Chandigarh", "India"), ("Hyderabad", "India"),
          ("New York", "USA"), ("San Francisco", "USA"), ("London", "UK"),
          ("Toronto", "Canada")]

CATEGORIES = {
    "Electronics": [("Wireless Mouse", 799), ("Bluetooth Earbuds", 1999),
                     ("USB-C Charger", 599), ("Smartwatch", 4999),
                     ("Laptop Stand", 1299), ("Mechanical Keyboard", 3499)],
    "Fashion": [("Cotton T-Shirt", 499), ("Denim Jacket", 2499),
                ("Running Shoes", 3299), ("Leather Wallet", 899),
                ("Sunglasses", 1199)],
    "Home & Kitchen": [("Non-stick Pan", 1099), ("Electric Kettle", 1499),
                        ("LED Desk Lamp", 799), ("Storage Organizer Set", 649)],
    "Books": [("Data Engineering Handbook", 899), ("Python Crash Course", 699),
              ("SQL for Analysts", 599)],
    "Sports": [("Yoga Mat", 799), ("Dumbbell Set 10kg", 2199),
               ("Cricket Bat", 1799)],
}

N_CUSTOMERS = 400
N_PRODUCTS = sum(len(v) for v in CATEGORIES.values())
DAYS_OF_HISTORY = 180  # ~6 months of daily transactions


def ensure_dirs():
    os.makedirs(RAW_DIR, exist_ok=True)


def generate_customers():
    customers = []
    for cid in range(1, N_CUSTOMERS + 1):
        fname = random.choice(FIRST_NAMES)
        lname = random.choice(LAST_NAMES)
        city, country = random.choice(CITIES)
        signup_date = date(2024, 1, 1) + timedelta(days=random.randint(0, 500))
        segment = random.choices(
            ["New", "Regular", "VIP"], weights=[0.4, 0.45, 0.15]
        )[0]
        customers.append({
            "customer_id": cid,
            "first_name": fname,
            "last_name": lname,
            "email": f"{fname.lower()}.{lname.lower()}{cid}@example.com",
            "city": city,
            "country": country,
            "signup_date": signup_date.isoformat(),
            "customer_segment": segment,
        })
    return customers


def generate_products():
    products = []
    pid = 1
    for category, items in CATEGORIES.items():
        for name, base_price in items:
            products.append({
                "product_id": pid,
                "product_name": name,
                "category": category,
                "unit_price": base_price,
                "cost_price": round(base_price * random.uniform(0.55, 0.75), 2),
            })
            pid += 1
    return products


def seasonal_factor(d: date) -> float:
    """Simulate real-world demand patterns: weekend bump + a festive
    sales spike in Oct/Nov (Diwali/Black-Friday style peak) + gentle
    month-over-month growth trend -- so the ML forecasting step later
    on has real signal to learn from, not pure noise."""
    weekday_factor = 1.35 if d.weekday() >= 5 else 1.0
    seasonal = 1.8 if d.month in (10, 11) else 1.0
    growth_trend = 1 + (d.toordinal() - date(2025, 3, 1).toordinal()) * 0.0015
    return max(weekday_factor * seasonal * growth_trend, 0.3)


def generate_orders(customers, products):
    orders = []
    order_items = []
    order_id = 1
    start = date.today() - timedelta(days=DAYS_OF_HISTORY)

    for offset in range(DAYS_OF_HISTORY):
        d = start + timedelta(days=offset)
        base_orders_today = int(18 * seasonal_factor(d))
        n_orders_today = max(1, int(random.gauss(base_orders_today, 4)))

        for _ in range(n_orders_today):
            cust = random.choice(customers)
            order_time = datetime.combine(d, datetime.min.time()) + timedelta(
                hours=random.randint(8, 22), minutes=random.randint(0, 59))
            n_items = random.choices([1, 2, 3, 4], weights=[0.5, 0.3, 0.15, 0.05])[0]
            chosen_products = random.sample(products, k=min(n_items, len(products)))

            order_total = 0.0
            for prod in chosen_products:
                qty = random.randint(1, 3)
                discount_pct = random.choices([0, 5, 10, 15], weights=[0.6, 0.2, 0.15, 0.05])[0]
                line_total = prod["unit_price"] * qty * (1 - discount_pct / 100)
                order_total += line_total
                order_items.append({
                    "order_item_id": len(order_items) + 1,
                    "order_id": order_id,
                    "product_id": prod["product_id"],
                    "quantity": qty,
                    "unit_price": prod["unit_price"],
                    "discount_pct": discount_pct,
                    "line_total": round(line_total, 2),
                })

            payment_method = random.choices(
                ["UPI", "Credit Card", "Debit Card", "Net Banking", "COD"],
                weights=[0.35, 0.25, 0.15, 0.1, 0.15]
            )[0]
            order_status = random.choices(
                ["Delivered", "Shipped", "Cancelled", "Returned"],
                weights=[0.82, 0.08, 0.06, 0.04]
            )[0]

            orders.append({
                "order_id": order_id,
                "customer_id": cust["customer_id"],
                "order_timestamp": order_time.isoformat(),
                "order_date": d.isoformat(),
                "payment_method": payment_method,
                "order_status": order_status,
                "order_total": round(order_total, 2),
            })
            order_id += 1

    return orders, order_items


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def run():
    ensure_dirs()
    customers = generate_customers()
    products = generate_products()
    orders, order_items = generate_orders(customers, products)

    write_csv(os.path.join(RAW_DIR, "customers.csv"), customers)
    write_csv(os.path.join(RAW_DIR, "products.csv"), products)
    write_csv(os.path.join(RAW_DIR, "orders.csv"), orders)
    write_csv(os.path.join(RAW_DIR, "order_items.csv"), order_items)

    print(f"[extract] {len(customers)} customers -> customers.csv")
    print(f"[extract] {len(products)} products -> products.csv")
    print(f"[extract] {len(orders)} orders -> orders.csv")
    print(f"[extract] {len(order_items)} order_items -> order_items.csv")
    print(f"[extract] raw files written to: {os.path.abspath(RAW_DIR)}")


if __name__ == "__main__":
    run()
