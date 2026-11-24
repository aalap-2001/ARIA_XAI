"""Synthetic demo businesses for Aria XAI. Everything here is invented for demonstrations.

Each business is described the way a real customer would arrive: a product description, documents, a connected
database, a team, and some weeks of history. scripts/seed_demo.py turns it into data through the product's own code
(rule engine, plans, decisions, Aria Watch, audit), so every record is consistent with the rules."""

PEAK = {
    "name": "Peak Outdoor Gear (demo)",
    "domain": "peakoutdoor.example",
    "description": (
        "Peak Outdoor Gear is an online shop for camping, climbing and hiking equipment, selling to about 40,000 customers in "
        "the UK and Ireland. Customers order on our website; orders ship from one warehouse in Leeds. Members of our loyalty "
        "programme (Silver and Gold tiers) get store credit and free returns. The support team handles returns, refunds and "
        "delivery problems; the buying team keeps stock above reorder levels and places purchase orders with suppliers. "
        "Good looks like: refunds within 3 days, no stock-outs on best sellers, fewer than 2% of orders delivered late."),
    "documents": {
        "returns-and-refunds-policy.md": (
            "# Returns and refunds policy\n\nCustomers may return items within 30 days of delivery for a full refund to the original "
            "payment method.\n\nItems must be unused and resellable. Our warehouse grades every return from 0 (damaged) to 1 (like new); "
            "items graded below 0.4 are not refunded and are sent back to the customer.\n\nFinal-sale items (clearance, marked FINAL) "
            "cannot be returned.\n\nA refund can never be larger than the amount the customer paid for the order.\n\nRefunds above 250 GBP "
            "are checked by a support lead before the money is sent."),
        "loyalty-programme.md": (
            "# Loyalty programme\n\nSilver members (lifetime spend above 500 GBP) and Gold members (above 1,500 GBP) receive store credit "
            "as an apology when an order is delivered more than 3 days late: 10 GBP for Silver, 25 GBP for Gold.\n\nStore credit is "
            "added to the customer's account and can be used on any future order. Credit for a single incident never exceeds 50 GBP."),
        "buying-and-stock-handbook.md": (
            "# Buying and stock handbook\n\nEvery product has a reorder level. When stock falls below it, the buying team raises a "
            "purchase order with the supplier.\n\nA single purchase order may not exceed 500 units. Purchase orders above 5,000 GBP in "
            "value need the head of buying.\n\nBest sellers (tents, sleeping bags, head torches) must never go out of stock during "
            "May to August."),
    },
    "database": {
        "name": "Shop database",
        "tables": {
            "customers": (["customer_id", "name", "tier", "city", "lifetime_value", "store_credit"], [
                ("C-1001", "Amelia Hart", "Gold", "Leeds", 2140.50, 0), ("C-1002", "Oliver Bennett", "Silver", "York", 720.00, 10),
                ("C-1003", "Isla Murphy", "Standard", "Dublin", 180.25, 0), ("C-1004", "Noah Patel", "Gold", "Manchester", 3310.00, 25),
                ("C-1005", "Grace Walsh", "Silver", "Cork", 655.40, 0), ("C-1006", "Leo Fraser", "Standard", "Edinburgh", 95.00, 0),
                ("C-1007", "Ava Thompson", "Gold", "Sheffield", 1890.75, 0), ("C-1008", "Jack O'Brien", "Silver", "Galway", 1010.10, 0),
                ("C-1009", "Mia Clarke", "Standard", "Bristol", 240.00, 0), ("C-1010", "Harry Evans", "Silver", "Cardiff", 860.00, 0)]),
            "orders": (["order_id", "customer_id", "placed_on", "total", "status", "days_since_delivery", "days_late", "final_sale", "refund_amount"], [
                (50781, "C-1001", "2026-10-02", 289.00, "delivered", 41, 0, 0, 0), (50790, "C-1003", "2026-10-04", 64.99, "delivered", 39, 1, 0, 0),
                (50802, "C-1004", "2026-10-11", 512.00, "delivered", 31, 0, 0, 0), (50811, "C-1002", "2026-10-15", 129.00, "delivered", 25, 5, 0, 0),
                (50817, "C-1007", "2026-10-21", 289.00, "delivered", 12, 0, 0, 0), (50824, "C-1005", "2026-10-24", 44.50, "delivered", 16, 0, 1, 0),
                (50829, "C-1008", "2026-10-27", 349.00, "delivered", 9, 4, 0, 0), (50833, "C-1006", "2026-10-29", 79.00, "delivered", 7, 0, 0, 0),
                (50840, "C-1009", "2026-11-01", 158.00, "delivered", 5, 0, 0, 0), (50846, "C-1010", "2026-11-03", 219.00, "shipped", 0, 2, 0, 0),
                (50851, "C-1001", "2026-11-05", 96.00, "shipped", 0, 0, 0, 0), (50857, "C-1004", "2026-11-07", 1120.00, "processing", 0, 0, 0, 0)]),
            "products": (["sku", "name", "category", "stock", "reorder_level", "unit_cost"], [
                ("TENT-2P", "Ridge 2-person tent", "Tents", 18, 40, 92.00), ("TENT-4P", "Basecamp 4-person tent", "Tents", 33, 20, 160.00),
                ("BAG-3S", "Three-season sleeping bag", "Sleeping", 12, 30, 41.00), ("TORCH-H", "Head torch 400", "Lighting", 140, 60, 9.50),
                ("ROPE-60", "Dynamic rope 60m", "Climbing", 9, 10, 88.00), ("BOOT-W", "Trail boot (women)", "Footwear", 64, 25, 47.00),
                ("STOVE-G", "Gas stove compact", "Cooking", 27, 15, 21.00), ("JACKET-R", "Rain shell jacket", "Clothing", 51, 30, 38.00)]),
            "purchase_orders": (["po_id", "sku", "quantity", "status", "raised_on"], [
                (7001, "TORCH-H", 200, "received", "2026-10-06"), (7002, "BOOT-W", 60, "received", "2026-10-19")]),
        },
        "key": {"purchase_orders": "po_id"},
    },
    "people": [("Daniel Reyes", "daniel.reyes", "Org admin"), ("Priya Shah", "priya.shah", "Builder"),
               ("Sofia Lindqvist", "sofia.lindqvist", "Reviewer"), ("Tom Okafor", "tom.okafor", "Operator"),
               ("Hannah Kelly", "hannah.kelly", "Operator")],
    "content": {
        "summary": ("Peak Outdoor Gear sells outdoor equipment online in the UK and Ireland. The agent team answers questions about "
                    "orders, customers and stock, and proposes refunds, loyalty credit and purchase orders that people approve."),
        "industry": "Online retail (outdoor equipment)", "business_model": "Direct-to-consumer e-commerce with a loyalty programme",
        "primary_users": ["Support agents", "Support leads", "Buying team", "Operations admin"],
        "ontology": [
            {"name": "Customer", "description": "A person who buys from the shop, with a loyalty tier and store credit.", "source": {"connection_id": "$DB", "table": "customers"},
             "key_fields": ["customer_id"], "fields": [{"name": "tier", "type": "string"}, {"name": "lifetime_value", "type": "number"}, {"name": "store_credit", "type": "number"}]},
            {"name": "Order", "description": "A purchase, its delivery status, lateness and any refund.", "source": {"connection_id": "$DB", "table": "orders"},
             "key_fields": ["order_id"], "fields": [{"name": "total", "type": "number"}, {"name": "status", "type": "string"}, {"name": "days_since_delivery", "type": "number"}]},
            {"name": "Product", "description": "An item in the catalogue with stock and a reorder level.", "source": {"connection_id": "$DB", "table": "products"},
             "key_fields": ["sku"], "fields": [{"name": "stock", "type": "number"}, {"name": "reorder_level", "type": "number"}]},
            {"name": "Purchase order", "description": "A request to a supplier for more stock.", "source": {"connection_id": "$DB", "table": "purchase_orders"}, "key_fields": ["po_id"], "fields": []},
        ],
        "facts": [
            {"name": "order_id", "type": "number", "description": "The order concerned"},
            {"name": "order_total", "type": "number", "description": "What the customer paid for the order", "unit": "GBP"},
            {"name": "days_since_delivery", "type": "number", "description": "Days between delivery and the return request"},
            {"name": "item_condition_score", "type": "number", "description": "Warehouse grading of the returned item, 0 damaged to 1 like new"},
            {"name": "final_sale", "type": "boolean", "description": "Whether the item was sold as final sale"},
            {"name": "refund_amount", "type": "number", "description": "Amount to refund", "unit": "GBP"},
            {"name": "customer_id", "type": "string", "description": "The customer concerned"},
            {"name": "customer_tier", "type": "string", "description": "Loyalty tier: Standard, Silver or Gold"},
            {"name": "days_late", "type": "number", "description": "Days the delivery was late"},
            {"name": "store_credit", "type": "number", "description": "Store credit to add", "unit": "GBP"},
            {"name": "sku", "type": "string", "description": "Product SKU"},
            {"name": "quantity", "type": "number", "description": "Units to order"},
        ],
        "signals": [
            {"id": "resellable", "description": "The returned item can be resold", "combine": "weighted_sum",
             "inputs": [{"fact": "item_condition_score", "weight": 1}], "assert_above": 0.6, "deny_below": 0.4},
        ],
        "rules": [
            {"id": "return_window", "description": "Returns are accepted within 30 days of delivery", "applies_to": ["ISSUE_REFUND"],
             "condition": {"path": "days_since_delivery", "op": "<=", "value": 30}, "on_fail": "INVALID", "message": "Outside the 30-day return window",
             "citation": "returns-and-refunds-policy.md p.1"},
            {"id": "not_final_sale", "description": "Final-sale items cannot be returned", "applies_to": ["ISSUE_REFUND"],
             "condition": {"path": "final_sale", "is": False}, "on_fail": "INVALID", "message": "The item was sold as final sale",
             "citation": "returns-and-refunds-policy.md p.1"},
            {"id": "item_resellable", "description": "Only unused, resellable items are refunded", "applies_to": ["ISSUE_REFUND"],
             "condition": {"path": "signals.resellable", "is": True}, "on_fail": "INVALID", "message": "The item was graded as not resellable",
             "citation": "returns-and-refunds-policy.md p.1"},
            {"id": "refund_within_paid", "description": "A refund can never exceed what the customer paid", "applies_to": ["ISSUE_REFUND"],
             "condition": {"path": "refund_amount", "op": "<=", "value": "$order_total"}, "on_fail": "INVALID", "message": "Refund is larger than the order total",
             "citation": "returns-and-refunds-policy.md p.1"},
            {"id": "credit_cap", "description": "Store credit for one incident is at most 50 GBP", "applies_to": ["ADD_STORE_CREDIT"],
             "condition": {"path": "store_credit", "op": "<=", "value": 50}, "on_fail": "INVALID", "message": "Credit above the 50 GBP cap",
             "citation": "loyalty-programme.md p.1"},
            {"id": "po_unit_cap", "description": "One purchase order is at most 500 units", "applies_to": ["RAISE_PURCHASE_ORDER"],
             "condition": {"path": "quantity", "op": "<=", "value": 500}, "on_fail": "INVALID", "message": "More than 500 units in one order",
             "citation": "buying-and-stock-handbook.md p.1"},
        ],
        "actions": [
            {"name": "ISSUE_REFUND", "description": "Refund an order to the original payment method", "risk": "MEDIUM", "amount_fact": "refund_amount",
             "required_facts": ["order_id", "order_total", "days_since_delivery", "item_condition_score", "final_sale", "refund_amount"],
             "owner_role": "Reviewer", "always_review": False, "auto_approve_below": 50,
             "executor": {"type": "database", "connection_id": "$DB", "table": "orders", "operation": "update", "key_column": "order_id", "columns": ["status", "refund_amount"]}},
            {"name": "ADD_STORE_CREDIT", "description": "Add apology store credit to a loyalty member's account", "risk": "LOW", "amount_fact": "store_credit",
             "required_facts": ["customer_id", "store_credit"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "customers", "operation": "update", "key_column": "customer_id", "columns": ["store_credit"]}},
            {"name": "RAISE_PURCHASE_ORDER", "description": "Raise a purchase order with the supplier", "risk": "HIGH", "amount_fact": "quantity",
             "required_facts": ["sku", "quantity"], "owner_role": "Org admin",
             "executor": {"type": "database", "connection_id": "$DB", "table": "purchase_orders", "operation": "insert", "columns": ["sku", "quantity", "status", "raised_on"]}},
        ],
        "watch_rules": [
            {"id": "stock_below_reorder", "event_type": "stock.changed", "when": {"path": "data.stock", "op": "<", "value": "$data.reorder_level"},
             "why": "A product dropped below its reorder level and could go out of stock", "owner_role": "Org admin"},
            {"id": "late_delivery_member", "event_type": "order.delivered", "when": {"all": [{"path": "data.days_late", "op": ">", "value": 3}, {"path": "data.tier", "op": "!=", "value": "Standard"}]},
             "why": "A loyalty member received a late delivery and is owed apology credit", "owner_role": "Reviewer"},
        ],
        "agents": [
            {"id": "order_specialist", "name": "Order specialist", "purpose": "Looks up orders, deliveries and refund history.",
             "instructions": "Answer from the orders and customers tables. Always quote the order id.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["orders", "customers"]}], "actions": ["ISSUE_REFUND", "ADD_STORE_CREDIT"]},
            {"id": "stock_specialist", "name": "Stock specialist", "purpose": "Watches stock levels and supplier orders.",
             "instructions": "Compare stock with reorder levels and recent purchase orders.", "tools": ["query_data", "search_knowledge"],
             "data_scope": [{"connection_id": "$DB", "tables": ["products", "purchase_orders"]}], "actions": ["RAISE_PURCHASE_ORDER"]},
        ],
        "kpis": [
            {"name": "Refund turnaround", "description": "Days from return request to refund", "how_to_measure": "Median days, target under 3"},
            {"name": "Stock-outs on best sellers", "description": "Days a best seller had zero stock", "how_to_measure": "Count per month, target 0"},
            {"name": "Late deliveries", "description": "Share of orders delivered late", "how_to_measure": "Orders with days_late > 0 / all orders, target under 2%"},
        ],
        "starter_questions": ["Which products are below their reorder level?", "Which loyalty members had a late delivery this month?",
                              "Can order 50817 be refunded?", "What is our refund policy for final-sale items?"],
    },
    "edits": [  # version 2: changes people made after Aria XAI's first understanding
        ("priya.shah", "rules", "add", None, {"id": "gold_priority_review", "description": "Refunds for Gold members above 500 GBP are reviewed by a lead",
                                             "applies_to": ["ISSUE_REFUND"], "condition": {"path": "refund_amount", "op": "<=", "value": 500},
                                             "on_fail": "INSUFFICIENT_EVIDENCE", "message": "Large refund, a support lead reviews it", "citation": "Agreed in support review, 14 Oct"}),
        ("priya.shah", "starter_questions", "add", None, "How much store credit did we give last month?"),
        ("priya.shah", "signals", "edit", "resellable", {"id": "resellable", "description": "The returned item can be resold", "combine": "weighted_sum",
                                                        "inputs": [{"fact": "item_condition_score", "weight": 1}], "assert_above": 0.6, "deny_below": 0.4}),
    ],
    "draft_edits": [("priya.shah", "kpis", "add", None, {"name": "Credit given per month", "description": "Store credit issued as apologies", "how_to_measure": "Sum of credit, GBP"})],
    "studio": {"interface": {"tone": "friendly"}, "motivation": {"watch_cooldown_minutes": 60}},
    "conversations": [
        {"by": "hannah.kelly", "days_ago": 19, "q": "Which products are below their reorder level?", "agent": "stock_specialist",
         "sql": "SELECT sku, name, stock, reorder_level FROM products WHERE stock < reorder_level ORDER BY stock",
         "answer": "{count} products are below their reorder level:\n\n{table}\n\nThe Ridge 2-person tent and the three-season sleeping bag are best sellers, so the handbook says they must not run out before summer."},
        {"by": "tom.okafor", "days_ago": 16, "q": "Customer Ava Thompson wants to return order 50817, the tent arrived 12 days ago and is unused. Please refund it.",
         "search": "return within 30 days unused resellable", "sql": "SELECT order_id, customer_id, total, days_since_delivery, final_sale FROM orders WHERE order_id = 50817",
         "answer": "Order 50817 (289 GBP) is inside the 30-day window, not final sale, and the warehouse graded the tent 0.95. I have prepared a refund plan for your approval below.",
         "plan": {"title": "Refund order 50817", "steps": [{"action": "ISSUE_REFUND", "summary": "Full refund of order 50817 to Ava Thompson",
                  "facts": {"order_id": 50817, "order_total": 289, "days_since_delivery": 12, "item_condition_score": 0.95, "final_sale": False, "refund_amount": 289},
                  "payload": {"order_id": 50817, "status": "refunded", "refund_amount": 289}}]},
         "decide": "approve", "review": ("sofia.lindqvist", True, "Checked the grading photos, refund approved.", 15)},
        {"by": "sofia.lindqvist", "days_ago": 14, "q": "Refund order 50781 in full, the customer says the tent leaks.",
         "search": "return window", "sql": "SELECT order_id, total, days_since_delivery FROM orders WHERE order_id = 50781",
         "answer": "Order 50781 was delivered 41 days ago, which is outside the 30-day return window, so the rule engine blocked the refund. A faulty-product claim goes through the manufacturer warranty instead.",
         "plan": {"title": "Refund order 50781", "steps": [{"action": "ISSUE_REFUND", "summary": "Refund order 50781",
                  "facts": {"order_id": 50781, "order_total": 289, "days_since_delivery": 41, "item_condition_score": 0.8, "final_sale": False, "refund_amount": 289},
                  "payload": {"order_id": 50781, "status": "refunded", "refund_amount": 289}}]}, "decide": "approve"},
        {"by": "daniel.reyes", "days_ago": 11, "q": "Order 50811 for Oliver Bennett arrived 5 days late. Give him the loyalty credit.",
         "search": "store credit late delivery Silver", "sql": "SELECT customer_id, name, tier, store_credit FROM customers WHERE customer_id = 'C-1002'",
         "answer": "Oliver is a Silver member, and the loyalty programme gives 10 GBP store credit for a delivery more than 3 days late. The credit plan is below.",
         "plan": {"title": "Add 10 GBP credit for Oliver Bennett", "steps": [{"action": "ADD_STORE_CREDIT", "summary": "Silver late-delivery credit",
                  "facts": {"customer_id": "C-1002", "customer_tier": "Silver", "days_late": 5, "store_credit": 10}, "payload": {"customer_id": "C-1002", "store_credit": 20}}]},
         "decide": "approve"},
        {"by": "hannah.kelly", "days_ago": 8, "q": "Refund order 50833, the customer changed their mind.",
         "sql": "SELECT order_id, total, days_since_delivery, final_sale FROM orders WHERE order_id = 50833",
         "answer": "Order 50833 (79 GBP) qualifies, but the warehouse has not graded the returned item yet. I prepared the plan; you may want to wait for the grading.",
         "plan": {"title": "Refund order 50833", "steps": [{"action": "ISSUE_REFUND", "summary": "Refund order 50833",
                  "facts": {"order_id": 50833, "order_total": 79, "days_since_delivery": 7, "final_sale": False, "refund_amount": 79},
                  "payload": {"order_id": 50833, "status": "refunded", "refund_amount": 79}}]}, "decide": "reject"},
        {"by": "daniel.reyes", "days_ago": 5, "q": "Raise a purchase order for 120 Ridge 2-person tents.",
         "search": "purchase order units", "sql": "SELECT sku, stock, reorder_level FROM products WHERE sku = 'TENT-2P'",
         "answer": "TENT-2P has 18 in stock against a reorder level of 40. A purchase order for 120 units is within the 500-unit cap. The plan is below.",
         "plan": {"title": "Purchase order: 120 x TENT-2P", "steps": [{"action": "RAISE_PURCHASE_ORDER", "summary": "Restock the Ridge 2-person tent",
                  "facts": {"sku": "TENT-2P", "quantity": 120}, "payload": {"sku": "TENT-2P", "quantity": 120, "status": "sent", "raised_on": "2026-11-08"}}]},
         "decide": "approve"},
        {"by": "tom.okafor", "days_ago": 2, "q": "Customer Noah Patel wants to return order 50802, can we refund it?",
         "sql": "SELECT order_id, total, days_since_delivery, final_sale FROM orders WHERE order_id = 50802",
         "answer": "Order 50802 (512 GBP) was delivered 31 days ago, one day outside the window. I prepared the plan so a lead can decide, but the rule engine will block it unless the policy is changed.",
         "plan": {"title": "Refund order 50802", "steps": [{"action": "ISSUE_REFUND", "summary": "Refund order 50802",
                  "facts": {"order_id": 50802, "order_total": 512, "days_since_delivery": 31, "item_condition_score": 0.9, "final_sale": False, "refund_amount": 512},
                  "payload": {"order_id": 50802, "status": "refunded", "refund_amount": 512}}]}, "decide": None},
        {"by": "priya.shah", "days_ago": 1, "q": "What is our refund policy for final-sale items?", "search": "final sale returned",
         "answer": "Final-sale items (clearance, marked FINAL) cannot be returned, so they are never refunded. The rule not_final_sale enforces this for every refund request."},
    ],
    "events": [  # what the shop sent to Aria Watch; most are ignored without calling the model
        {"type": "order.delivered", "entity_id": "50840", "data": {"days_late": 0, "tier": "Standard"}, "days_ago": 6},
        {"type": "order.delivered", "entity_id": "50829", "data": {"days_late": 4, "tier": "Silver", "customer_id": "C-1008"}, "days_ago": 9,
         "suggest": {"title": "Add 10 GBP apology credit for Jack O'Brien", "rationale": "Order 50829 arrived 4 days late and Jack is a Silver member.",
                     "benefit": "Keeps a 1,010 GBP lifetime customer happy, as the loyalty programme promises.",
                     "steps": [{"action": "ADD_STORE_CREDIT", "summary": "Silver late-delivery credit", "facts": {"customer_id": "C-1008", "customer_tier": "Silver", "days_late": 4, "store_credit": 10},
                                "payload": {"customer_id": "C-1008", "store_credit": 10}}], "decide": ("sofia.lindqvist", True, 8)}},
        {"type": "stock.changed", "entity_id": "TORCH-H", "data": {"stock": 140, "reorder_level": 60}, "days_ago": 7},
        {"type": "stock.changed", "entity_id": "BAG-3S", "data": {"stock": 12, "reorder_level": 30}, "days_ago": 3,
         "suggest": {"title": "Raise a purchase order for 150 three-season sleeping bags", "rationale": "BAG-3S fell to 12 units against a reorder level of 30.",
                     "benefit": "Sleeping bags are a best seller and must not go out of stock before summer.",
                     "steps": [{"action": "RAISE_PURCHASE_ORDER", "summary": "Restock BAG-3S", "facts": {"sku": "BAG-3S", "quantity": 150},
                                "payload": {"sku": "BAG-3S", "quantity": 150, "status": "sent", "raised_on": "2026-11-10"}}]}},
        {"type": "stock.changed", "entity_id": "ROPE-60", "data": {"stock": 9, "reorder_level": 10}, "days_ago": 1,
         "suggest": {"title": "Raise a purchase order for 30 dynamic ropes", "rationale": "ROPE-60 is at 9 units, just under its reorder level of 10.",
                     "benefit": "Avoids a stock-out on a climbing essential.",
                     "steps": [{"action": "RAISE_PURCHASE_ORDER", "summary": "Restock ROPE-60", "facts": {"sku": "ROPE-60", "quantity": 30},
                                "payload": {"sku": "ROPE-60", "quantity": 30, "status": "sent", "raised_on": "2026-11-12"}}]}},
        {"type": "order.placed", "entity_id": "50857", "data": {"total": 1120}, "days_ago": 6},
        {"type": "review.posted", "entity_id": "TENT-4P", "data": {"stars": 5}, "days_ago": 4},
        {"type": "order.delivered", "entity_id": "50846", "data": {"days_late": 2, "tier": "Silver"}, "days_ago": 2},
        {"type": "order.delivered", "entity_id": "50790", "data": {"days_late": 1, "tier": "Standard"}, "days_ago": 12},
        {"type": "order.placed", "entity_id": "50851", "data": {"total": 96}, "days_ago": 8},
    ],
}

LUMEN = {
    "name": "Lumen Dental Clinics (demo)",
    "domain": "lumendental.example",
    "description": (
        "Lumen Dental runs six dental clinics in the Midlands. Patients book check-ups, hygiene visits and treatments online or "
        "by phone; each booking takes a deposit. Reception teams handle cancellations, deposit refunds and no-show fees; clinic "
        "managers approve treatment discounts; the operations team fills empty chair time from the waiting list. Good looks like: "
        "chair utilisation above 85%, no-show rate under 5%, and deposit refunds handled the same day."),
    "documents": {
        "cancellation-and-deposit-policy.md": (
            "# Cancellation and deposit policy\n\nEvery booking takes a deposit (25 GBP for check-ups, 50 GBP for treatments).\n\n"
            "Patients who cancel at least 48 hours before the appointment get the full deposit back.\n\nCancellations with less than 48 "
            "hours' notice and no-shows keep the deposit as a fee, unless the clinic manager waives it for a medical emergency.\n\n"
            "A deposit refund can never be more than the deposit paid."),
        "treatment-discounts.md": (
            "# Treatment discounts\n\nPatients on the Lumen Care plan get 10% off treatments. Clinic managers may approve an extra "
            "goodwill discount of up to 15% for a complaint that was upheld.\n\nDiscounts above 25% in total are never allowed."),
        "waiting-list-guide.md": (
            "# Waiting list guide\n\nWhen an appointment is cancelled, the slot is offered to the first patient on the waiting list for "
            "the same clinic and treatment type.\n\nOffers expire after 2 hours. Patients with urgent flags are offered slots first."),
    },
    "database": {
        "name": "Practice management system",
        "tables": {
            "patients": (["patient_id", "name", "plan", "clinic", "no_shows"], [
                ("P-201", "Ruth Adeyemi", "Lumen Care", "Derby", 0), ("P-202", "Callum Reid", "None", "Leicester", 2),
                ("P-203", "Sana Iqbal", "Lumen Care", "Nottingham", 0), ("P-204", "George Hill", "None", "Derby", 1),
                ("P-205", "Elena Rossi", "Lumen Care", "Coventry", 0), ("P-206", "Marcus Lee", "None", "Leicester", 0),
                ("P-207", "Fatima Noor", "Lumen Care", "Nottingham", 3), ("P-208", "Ben Carter", "None", "Coventry", 0)]),
            "appointments": (["appointment_id", "patient_id", "clinic", "treatment", "starts_at", "deposit", "status", "hours_notice", "deposit_refunded"], [
                (9101, "P-201", "Derby", "Check-up", "2026-11-14 09:00", 25, "cancelled", 72, 0), (9102, "P-202", "Leicester", "Filling", "2026-11-13 11:30", 50, "no_show", 0, 0),
                (9103, "P-203", "Nottingham", "Hygiene", "2026-11-15 14:00", 25, "booked", 0, 0), (9104, "P-204", "Derby", "Crown", "2026-11-12 10:00", 50, "cancelled", 20, 0),
                (9105, "P-205", "Coventry", "Check-up", "2026-11-18 16:00", 25, "booked", 0, 0), (9106, "P-206", "Leicester", "Whitening", "2026-11-11 15:00", 50, "completed", 0, 0),
                (9107, "P-207", "Nottingham", "Filling", "2026-11-10 09:30", 50, "no_show", 0, 0), (9108, "P-208", "Coventry", "Check-up", "2026-11-20 08:30", 25, "booked", 0, 0),
                (9109, "P-201", "Derby", "Hygiene", "2026-11-21 12:00", 25, "booked", 0, 0), (9110, "P-203", "Nottingham", "Crown", "2026-11-25 10:30", 50, "booked", 0, 0)]),
            "waiting_list": (["entry_id", "patient_id", "clinic", "treatment", "urgent", "status"], [
                (301, "P-206", "Derby", "Check-up", 0, "waiting"), (302, "P-208", "Derby", "Crown", 1, "waiting"), (303, "P-204", "Nottingham", "Hygiene", 0, "waiting")]),
            "discounts": (["discount_id", "patient_id", "treatment", "percent", "reason"], [(41, "P-205", "Crown", 10, "Lumen Care plan")]),
        },
        "key": {"discounts": "discount_id"},
    },
    "people": [("Helen Brooks", "helen.brooks", "Org admin"), ("Arjun Mehta", "arjun.mehta", "Builder"),
               ("Dr Claire Dawson", "claire.dawson", "Reviewer"), ("Kofi Mensah", "kofi.mensah", "Operator"),
               ("Laura Price", "laura.price", "Operator")],
    "content": {
        "summary": ("Lumen Dental runs six clinics. The agent team answers questions about appointments, patients and the waiting list, "
                    "and proposes deposit refunds, waived fees, discounts and waiting-list offers that staff approve."),
        "industry": "Healthcare (dental clinics)", "business_model": "Private and plan-based dental care across six clinics",
        "primary_users": ["Receptionists", "Clinic managers", "Operations team"],
        "ontology": [
            {"name": "Patient", "description": "A person registered at a clinic, with a care plan and no-show history.", "source": {"connection_id": "$DB", "table": "patients"}, "key_fields": ["patient_id"], "fields": [{"name": "plan", "type": "string"}, {"name": "no_shows", "type": "number"}]},
            {"name": "Appointment", "description": "A booking with a deposit, a status and the notice given if cancelled.", "source": {"connection_id": "$DB", "table": "appointments"}, "key_fields": ["appointment_id"], "fields": [{"name": "deposit", "type": "number"}, {"name": "hours_notice", "type": "number"}]},
            {"name": "Waiting list entry", "description": "A patient waiting for an earlier slot.", "source": {"connection_id": "$DB", "table": "waiting_list"}, "key_fields": ["entry_id"], "fields": [{"name": "urgent", "type": "boolean"}]},
            {"name": "Discount", "description": "A percentage discount on a treatment.", "source": {"connection_id": "$DB", "table": "discounts"}, "key_fields": ["discount_id"], "fields": []},
        ],
        "facts": [
            {"name": "appointment_id", "type": "number", "description": "The appointment concerned"},
            {"name": "hours_notice", "type": "number", "description": "Hours between the cancellation and the appointment"},
            {"name": "deposit_paid", "type": "number", "description": "Deposit the patient paid", "unit": "GBP"},
            {"name": "refund_amount", "type": "number", "description": "Deposit to refund", "unit": "GBP"},
            {"name": "medical_emergency", "type": "boolean", "description": "The patient missed it because of a medical emergency"},
            {"name": "patient_id", "type": "string", "description": "The patient concerned"},
            {"name": "discount_percent", "type": "number", "description": "Total discount on the treatment", "unit": "%"},
            {"name": "complaint_upheld", "type": "boolean", "description": "A complaint about the treatment was upheld"},
            {"name": "urgent", "type": "boolean", "description": "The waiting patient has an urgent flag"},
        ],
        "signals": [
            {"id": "genuine_emergency", "description": "The missed appointment was likely a genuine emergency", "combine": "noisy_or",
             "inputs": [{"fact": "medical_emergency", "weight": 0.9}], "assert_above": 0.7, "deny_below": 0.3},
        ],
        "rules": [
            {"id": "notice_48h", "description": "Full deposit refunds need at least 48 hours' notice", "applies_to": ["REFUND_DEPOSIT"],
             "condition": {"path": "hours_notice", "op": ">=", "value": 48}, "on_fail": "INVALID", "message": "Less than 48 hours' notice", "citation": "cancellation-and-deposit-policy.md p.1"},
            {"id": "refund_not_above_deposit", "description": "A refund can never exceed the deposit paid", "applies_to": ["REFUND_DEPOSIT"],
             "condition": {"path": "refund_amount", "op": "<=", "value": "$deposit_paid"}, "on_fail": "INVALID", "message": "Refund above the deposit", "citation": "cancellation-and-deposit-policy.md p.1"},
            {"id": "waiver_needs_emergency", "description": "A no-show fee is only waived for a medical emergency", "applies_to": ["WAIVE_NO_SHOW_FEE"],
             "condition": {"path": "signals.genuine_emergency", "is": True}, "on_fail": "INSUFFICIENT_EVIDENCE", "message": "No evidence of a medical emergency", "citation": "cancellation-and-deposit-policy.md p.1"},
            {"id": "discount_cap", "description": "Total discounts never exceed 25%", "applies_to": ["APPLY_DISCOUNT"],
             "condition": {"path": "discount_percent", "op": "<=", "value": 25}, "on_fail": "INVALID", "message": "Above the 25% cap", "citation": "treatment-discounts.md p.1"},
        ],
        "actions": [
            {"name": "REFUND_DEPOSIT", "description": "Refund a cancelled appointment's deposit", "risk": "LOW", "amount_fact": "refund_amount",
             "required_facts": ["appointment_id", "hours_notice", "deposit_paid", "refund_amount"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "appointments", "operation": "update", "key_column": "appointment_id", "columns": ["deposit_refunded"]}},
            {"name": "WAIVE_NO_SHOW_FEE", "description": "Return a no-show deposit for a medical emergency", "risk": "MEDIUM", "amount_fact": "refund_amount",
             "required_facts": ["appointment_id", "medical_emergency", "refund_amount"], "owner_role": "Reviewer", "always_review": True,
             "executor": {"type": "database", "connection_id": "$DB", "table": "appointments", "operation": "update", "key_column": "appointment_id", "columns": ["deposit_refunded", "status"]}},
            {"name": "APPLY_DISCOUNT", "description": "Record a treatment discount", "risk": "MEDIUM", "amount_fact": "discount_percent",
             "required_facts": ["patient_id", "discount_percent"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "discounts", "operation": "insert", "columns": ["patient_id", "treatment", "percent", "reason"]}},
            {"name": "OFFER_SLOT", "description": "Offer a freed slot to a waiting-list patient", "risk": "LOW", "required_facts": ["patient_id"], "owner_role": "Org admin",
             "executor": {"type": "database", "connection_id": "$DB", "table": "waiting_list", "operation": "update", "key_column": "entry_id", "columns": ["status"]}},
        ],
        "watch_rules": [
            {"id": "slot_freed", "event_type": "appointment.cancelled", "why": "A slot was freed and could be offered to the waiting list", "owner_role": "Org admin"},
            {"id": "repeat_no_show", "event_type": "appointment.no_show", "when": {"path": "data.no_shows", "op": ">=", "value": 3},
             "why": "A patient keeps missing appointments; the clinic may need to follow up", "owner_role": "Reviewer"},
        ],
        "agents": [
            {"id": "booking_specialist", "name": "Booking specialist", "purpose": "Looks up appointments, deposits and cancellations.",
             "instructions": "Answer from the appointments table; always give the appointment id and clinic.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["appointments", "patients"]}], "actions": ["REFUND_DEPOSIT", "WAIVE_NO_SHOW_FEE"]},
            {"id": "schedule_specialist", "name": "Schedule specialist", "purpose": "Fills empty chair time from the waiting list.",
             "instructions": "Prefer urgent patients, then the oldest entry for the same clinic and treatment.", "tools": ["query_data", "search_knowledge"],
             "data_scope": [{"connection_id": "$DB", "tables": ["waiting_list", "appointments"]}], "actions": ["OFFER_SLOT"]},
        ],
        "kpis": [
            {"name": "Chair utilisation", "description": "Share of bookable time that was booked", "how_to_measure": "Booked hours / available hours, target above 85%"},
            {"name": "No-show rate", "description": "Appointments missed without notice", "how_to_measure": "No-shows / appointments, target under 5%"},
            {"name": "Same-day deposit refunds", "description": "Refunds handled on the day of cancellation", "how_to_measure": "Share of refunds, target 100%"},
        ],
        "starter_questions": ["Which appointments were cancelled this week?", "Who is first on the Derby waiting list?",
                              "Can we refund the deposit for appointment 9101?", "Which patients have missed 3 or more appointments?"],
    },
    "edits": [
        ("arjun.mehta", "rules", "add", None, {"id": "discount_needs_complaint", "description": "Goodwill discounts above the plan discount need an upheld complaint",
                                              "applies_to": ["APPLY_DISCOUNT"], "condition": {"any": [{"path": "discount_percent", "op": "<=", "value": 10}, {"path": "complaint_upheld", "is": True}]},
                                              "on_fail": "INVALID", "message": "Extra discount without an upheld complaint", "citation": "treatment-discounts.md p.1"}),
        ("arjun.mehta", "starter_questions", "add", None, "How many no-shows did each clinic have this month?"),
    ],
    "draft_edits": [],
    "studio": {"interface": {"tone": "formal", "reply_length": "short"}},
    "conversations": [
        {"by": "laura.price", "days_ago": 13, "q": "Which patients have missed 3 or more appointments?",
         "sql": "SELECT patient_id, name, clinic, no_shows FROM patients WHERE no_shows >= 3", "answer": "{count} patient has missed 3 or more appointments:\n\n{table}\n\nThe policy keeps the deposit as a no-show fee unless the clinic manager waives it for a medical emergency."},
        {"by": "kofi.mensah", "days_ago": 10, "q": "Ruth Adeyemi cancelled appointment 9101 three days ahead. Refund her deposit.",
         "search": "cancel 48 hours deposit back", "sql": "SELECT appointment_id, deposit, hours_notice, status FROM appointments WHERE appointment_id = 9101",
         "answer": "Ruth cancelled 72 hours ahead, more than the 48 hours the policy requires, so the full 25 GBP deposit can be refunded. The plan is below.",
         "plan": {"title": "Refund deposit for appointment 9101", "steps": [{"action": "REFUND_DEPOSIT", "summary": "Full deposit refund, 72 hours' notice",
                  "facts": {"appointment_id": 9101, "hours_notice": 72, "deposit_paid": 25, "refund_amount": 25}, "payload": {"appointment_id": 9101, "deposit_refunded": 25}}]},
         "decide": "approve"},
        {"by": "kofi.mensah", "days_ago": 9, "q": "George Hill cancelled appointment 9104 yesterday for today. Refund the 50 GBP deposit.",
         "sql": "SELECT appointment_id, deposit, hours_notice FROM appointments WHERE appointment_id = 9104",
         "answer": "George gave 20 hours' notice, under the 48 hours required, so the rule engine blocked the refund. The deposit stays as a late-cancellation fee unless a manager waives it.",
         "plan": {"title": "Refund deposit for appointment 9104", "steps": [{"action": "REFUND_DEPOSIT", "summary": "Deposit refund",
                  "facts": {"appointment_id": 9104, "hours_notice": 20, "deposit_paid": 50, "refund_amount": 50}, "payload": {"appointment_id": 9104, "deposit_refunded": 50}}]},
         "decide": "approve"},
        {"by": "laura.price", "days_ago": 6, "q": "Fatima Noor missed appointment 9107 because she was in hospital. Can we waive the fee?",
         "search": "no-show medical emergency waive", "sql": "SELECT appointment_id, deposit, status FROM appointments WHERE appointment_id = 9107",
         "answer": "The policy allows a waiver for a medical emergency, and this action always goes to the clinic manager. I prepared the plan; Dr Dawson will decide.",
         "plan": {"title": "Waive no-show fee for appointment 9107", "steps": [{"action": "WAIVE_NO_SHOW_FEE", "summary": "Hospital admission, fee waiver",
                  "facts": {"appointment_id": 9107, "medical_emergency": True, "refund_amount": 50}, "payload": {"appointment_id": 9107, "deposit_refunded": 50, "status": "waived"}}]},
         "decide": "approve", "review": ("claire.dawson", True, "Discharge letter seen. Fee waived.", 5)},
        {"by": "helen.brooks", "days_ago": 3, "q": "Give Elena Rossi a 30% discount on her crown, the first fitting was poor.",
         "search": "discount cap complaint", "answer": "A 30% discount is above the 25% cap in the discounts policy, so the rule engine blocked it. The most I can propose is 25%: 10% plan discount plus 15% goodwill for an upheld complaint.",
         "plan": {"title": "30% discount for Elena Rossi", "steps": [{"action": "APPLY_DISCOUNT", "summary": "Goodwill discount on crown",
                  "facts": {"patient_id": "P-205", "discount_percent": 30, "complaint_upheld": True}, "payload": {"patient_id": "P-205", "treatment": "Crown", "percent": 30, "reason": "Complaint upheld"}}]},
         "decide": "approve"},
        {"by": "kofi.mensah", "days_ago": 1, "q": "Who is first on the Derby waiting list?",
         "sql": "SELECT entry_id, patient_id, treatment, urgent FROM waiting_list WHERE clinic = 'Derby' AND status = 'waiting' ORDER BY urgent DESC, entry_id",
         "answer": "There are {count} patients waiting at Derby:\n\n{table}\n\nUrgent patients are offered slots first, so entry 302 is next."},
    ],
    "events": [
        {"type": "appointment.booked", "entity_id": "9110", "data": {"clinic": "Nottingham"}, "days_ago": 12},
        {"type": "appointment.cancelled", "entity_id": "9101", "data": {"clinic": "Derby", "treatment": "Check-up"}, "days_ago": 10,
         "suggest": {"title": "Offer the freed Derby slot to Marcus Lee", "rationale": "Appointment 9101 at Derby was cancelled; Marcus is waiting for a Derby check-up.",
                     "benefit": "Fills 30 minutes of chair time that would otherwise be empty.",
                     "steps": [{"action": "OFFER_SLOT", "summary": "Offer the slot", "facts": {"patient_id": "P-206"}, "payload": {"entry_id": 301, "status": "offered"}}],
                     "decide": ("helen.brooks", True, 10)}},
        {"type": "appointment.no_show", "entity_id": "9107", "data": {"patient_id": "P-207", "no_shows": 3}, "days_ago": 7,
         "suggest": {"title": "Follow up with Fatima Noor about repeated missed appointments", "rationale": "Fatima has now missed 3 appointments.",
                     "benefit": "A call can rebook her and protect chair time.", "steps": [{"action": "OFFER_SLOT", "summary": "Offer a new slot", "facts": {"patient_id": "P-207"}, "payload": {"entry_id": 303, "status": "offered"}}]}},
        {"type": "appointment.no_show", "entity_id": "9102", "data": {"patient_id": "P-202", "no_shows": 2}, "days_ago": 1},
        {"type": "appointment.completed", "entity_id": "9106", "data": {"clinic": "Leicester"}, "days_ago": 2},
        {"type": "appointment.cancelled", "entity_id": "9104", "data": {"clinic": "Derby", "treatment": "Crown"}, "days_ago": 1,
         "suggest": {"title": "Offer the freed Derby crown slot to Ben Carter (urgent)", "rationale": "Appointment 9104 was cancelled; Ben is urgent and waiting for a Derby crown.",
                     "benefit": "Treats an urgent patient sooner and fills an hour of chair time.",
                     "steps": [{"action": "OFFER_SLOT", "summary": "Offer the slot", "facts": {"patient_id": "P-208", "urgent": True}, "payload": {"entry_id": 302, "status": "offered"}}]}},
    ],
}

BRIGHTLINE = {
    "name": "Brightline Freight (demo)",
    "domain": "brightlinefreight.example",
    "description": (
        "Brightline Freight moves palletised goods for about 300 business customers across Europe using its own trucks and partner "
        "carriers. Customers book shipments through our portal or API. Dispatchers assign carriers, the customer service team "
        "handles delays and damage claims, and finance issues credit notes. Contracts promise compensation when a shipment is "
        "more than 24 hours late. Good looks like: 96% of shipments on time, claims settled within 10 days, carrier costs under budget."),
    "documents": {
        "service-level-agreement.md": (
            "# Service level agreement\n\nShipments delivered more than 24 hours after the promised time earn a credit of 5% of the "
            "freight charge per full day late, capped at 30%.\n\nNo credit is due for delays caused by customs holds or severe weather.\n\n"
            "Credit notes above 2,000 EUR are approved by finance."),
        "damage-claims-procedure.md": (
            "# Damage claims procedure\n\nClaims must be raised within 7 days of delivery with photos.\n\nCompensation is limited to "
            "8.33 SDR per kg of damaged goods, the CMR convention limit, unless the customer bought declared-value cover.\n\n"
            "Claims above 5,000 EUR are reviewed by the claims manager."),
        "carrier-assignment-rules.md": (
            "# Carrier assignment rules\n\nOnly carriers with an active contract and a safety rating of at least 4 may be assigned.\n\n"
            "Hazardous goods need an ADR-certified carrier.\n\nReassigning a shipment that is already in transit needs the operations lead."),
    },
    "database": {
        "name": "Transport management system",
        "tables": {
            "customers": (["customer_id", "name", "country", "account_tier"], [
                ("K-01", "Nordwerk GmbH", "DE", "Key"), ("K-02", "Vela Foods BV", "NL", "Standard"), ("K-03", "Ostrava Steel a.s.", "CZ", "Key"),
                ("K-04", "Atlas Pharma SA", "BE", "Key"), ("K-05", "Lumo Furniture Oy", "FI", "Standard")]),
            "shipments": (["shipment_id", "customer_id", "origin", "destination", "freight_charge", "hours_late", "delay_cause", "status", "carrier_id", "hazardous", "credit_issued"], [
                ("SH-4410", "K-01", "Hamburg", "Lyon", 3200, 52, "carrier", "delivered", "CR-2", 0, 0), ("SH-4415", "K-02", "Rotterdam", "Milan", 2100, 30, "customs", "delivered", "CR-1", 0, 0),
                ("SH-4421", "K-03", "Ostrava", "Antwerp", 4800, 0, "", "delivered", "CR-3", 0, 0), ("SH-4427", "K-04", "Brussels", "Vienna", 2750, 75, "carrier", "delivered", "CR-2", 1, 0),
                ("SH-4433", "K-05", "Helsinki", "Gdansk", 1900, 0, "", "in_transit", "CR-4", 0, 0), ("SH-4438", "K-01", "Munich", "Madrid", 3900, 0, "", "in_transit", "CR-1", 0, 0),
                ("SH-4442", "K-02", "Utrecht", "Prague", 1650, 26, "weather", "delivered", "CR-3", 0, 0), ("SH-4446", "K-04", "Liege", "Warsaw", 3100, 0, "", "booked", "", 1, 0)]),
            "carriers": (["carrier_id", "name", "safety_rating", "adr_certified", "contract_active"], [
                ("CR-1", "Eurohaul Logistics", 4.6, 1, 1), ("CR-2", "TransAlp Cargo", 3.8, 0, 1), ("CR-3", "Baltic Route", 4.2, 0, 1), ("CR-4", "Nordic Line", 4.9, 1, 1), ("CR-5", "QuickVan", 3.1, 0, 0)]),
            "credit_notes": (["credit_id", "shipment_id", "amount", "reason"], [(801, "SH-4402", 160, "24h+ late, 1 day")]),
        },
        "key": {"credit_notes": "credit_id"},
    },
    "people": [("Lena Vogel", "lena.vogel", "Org admin"), ("Mateo Silva", "mateo.silva", "Builder"),
               ("Ingrid Larsen", "ingrid.larsen", "Reviewer"), ("Piotr Nowak", "piotr.nowak", "Operator"),
               ("Chloe Martin", "chloe.martin", "Operator")],
    "content": {
        "summary": ("Brightline Freight moves palletised goods across Europe. The agent team tracks shipments and carriers, and proposes "
                    "late-delivery credits, carrier assignments and claim settlements that dispatchers and finance approve."),
        "industry": "Logistics (road freight)", "business_model": "B2B freight forwarding with own fleet and partner carriers",
        "primary_users": ["Dispatchers", "Customer service", "Finance", "Operations lead"],
        "ontology": [
            {"name": "Customer account", "description": "A business that ships with us.", "source": {"connection_id": "$DB", "table": "customers"}, "key_fields": ["customer_id"], "fields": [{"name": "account_tier", "type": "string"}]},
            {"name": "Shipment", "description": "A booked movement of goods, with lateness, cause and carrier.", "source": {"connection_id": "$DB", "table": "shipments"}, "key_fields": ["shipment_id"], "fields": [{"name": "freight_charge", "type": "number"}, {"name": "hours_late", "type": "number"}]},
            {"name": "Carrier", "description": "A trucking company we contract.", "source": {"connection_id": "$DB", "table": "carriers"}, "key_fields": ["carrier_id"], "fields": [{"name": "safety_rating", "type": "number"}]},
            {"name": "Credit note", "description": "Compensation issued to a customer.", "source": {"connection_id": "$DB", "table": "credit_notes"}, "key_fields": ["credit_id"], "fields": []},
        ],
        "facts": [
            {"name": "shipment_id", "type": "string", "description": "The shipment concerned"},
            {"name": "hours_late", "type": "number", "description": "Hours after the promised delivery time"},
            {"name": "delay_cause", "type": "string", "description": "carrier, customs, weather or other"},
            {"name": "freight_charge", "type": "number", "description": "What the customer paid for the shipment", "unit": "EUR"},
            {"name": "credit_amount", "type": "number", "description": "Credit to issue", "unit": "EUR"},
            {"name": "carrier_safety_rating", "type": "number", "description": "Safety rating of the carrier, 1 to 5"},
            {"name": "carrier_adr_certified", "type": "boolean", "description": "The carrier may move hazardous goods"},
            {"name": "hazardous", "type": "boolean", "description": "The shipment contains hazardous goods"},
            {"name": "carrier_id", "type": "string", "description": "Carrier to assign"},
        ],
        "signals": [
            {"id": "carrier_reliable", "description": "The carrier is reliable enough to assign", "combine": "weighted_sum",
             "inputs": [{"fact": "carrier_safety_rating", "weight": 1, "min": 1, "max": 5}], "assert_above": 0.75, "deny_below": 0.5},
        ],
        "rules": [
            {"id": "late_over_24h", "description": "Credit is only due for more than 24 hours late", "applies_to": ["ISSUE_LATE_CREDIT"],
             "condition": {"path": "hours_late", "op": ">", "value": 24}, "on_fail": "INVALID", "message": "Not more than 24 hours late", "citation": "service-level-agreement.md p.1"},
            {"id": "no_credit_force_majeure", "description": "No credit for customs holds or severe weather", "applies_to": ["ISSUE_LATE_CREDIT"],
             "condition": {"path": "delay_cause", "op": "in", "value": ["carrier", "other"]}, "on_fail": "INVALID", "message": "Delay caused by customs or weather", "citation": "service-level-agreement.md p.1"},
            {"id": "credit_cap_30", "description": "Credit is capped at 30% of the freight charge", "applies_to": ["ISSUE_LATE_CREDIT"],
             "condition": {"path": "credit_amount", "op": "<=", "value": "$freight_charge"}, "on_fail": "INVALID", "message": "Credit larger than the freight charge", "citation": "service-level-agreement.md p.1"},
            {"id": "adr_for_hazardous", "description": "Hazardous goods need an ADR-certified carrier", "applies_to": ["ASSIGN_CARRIER"],
             "condition": {"any": [{"path": "hazardous", "is": False}, {"path": "carrier_adr_certified", "is": True}]}, "on_fail": "INVALID", "message": "Carrier is not ADR certified", "citation": "carrier-assignment-rules.md p.1"},
            {"id": "carrier_safe", "description": "Only carriers with a safety rating of at least 4", "applies_to": ["ASSIGN_CARRIER"],
             "condition": {"path": "signals.carrier_reliable", "is": True}, "on_fail": "INVALID", "message": "Carrier safety rating too low", "citation": "carrier-assignment-rules.md p.1"},
        ],
        "actions": [
            {"name": "ISSUE_LATE_CREDIT", "description": "Issue a credit note for a late shipment", "risk": "MEDIUM", "amount_fact": "credit_amount",
             "required_facts": ["shipment_id", "hours_late", "delay_cause", "freight_charge", "credit_amount"], "owner_role": "Reviewer", "auto_approve_below": 200,
             "executor": {"type": "database", "connection_id": "$DB", "table": "credit_notes", "operation": "insert", "columns": ["shipment_id", "amount", "reason"]}},
            {"name": "ASSIGN_CARRIER", "description": "Assign a carrier to a booked shipment", "risk": "LOW", "required_facts": ["shipment_id", "carrier_id", "hazardous"], "owner_role": "Org admin",
             "executor": {"type": "database", "connection_id": "$DB", "table": "shipments", "operation": "update", "key_column": "shipment_id", "columns": ["carrier_id"]}},
        ],
        "watch_rules": [
            {"id": "shipment_late", "event_type": "shipment.delivered", "when": {"all": [{"path": "data.hours_late", "op": ">", "value": 24}, {"path": "data.delay_cause", "op": "==", "value": "carrier"}]},
             "why": "A shipment arrived more than 24 hours late through the carrier's fault; the contract promises a credit", "owner_role": "Reviewer"},
            {"id": "booked_without_carrier", "event_type": "shipment.booked", "when": {"path": "data.carrier_id", "op": "==", "value": ""},
             "why": "A shipment has no carrier yet and could miss its pickup", "owner_role": "Org admin"},
        ],
        "agents": [
            {"id": "shipment_specialist", "name": "Shipment specialist", "purpose": "Tracks shipments, delays and credits.",
             "instructions": "Answer from the shipments and credit_notes tables. Quote shipment ids.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["shipments", "credit_notes", "customers"]}], "actions": ["ISSUE_LATE_CREDIT"]},
            {"id": "carrier_specialist", "name": "Carrier specialist", "purpose": "Chooses compliant, safe carriers.",
             "instructions": "Check contract, safety rating and ADR certification before suggesting a carrier.", "tools": ["query_data", "search_knowledge"],
             "data_scope": [{"connection_id": "$DB", "tables": ["carriers", "shipments"]}], "actions": ["ASSIGN_CARRIER"]},
        ],
        "kpis": [
            {"name": "On-time delivery", "description": "Shipments delivered within 24 hours of the promise", "how_to_measure": "Share of delivered shipments, target 96%"},
            {"name": "Credits issued", "description": "Late-delivery compensation paid", "how_to_measure": "Sum per month in EUR"},
            {"name": "Claim settlement time", "description": "Days from claim to settlement", "how_to_measure": "Median, target under 10 days"},
        ],
        "starter_questions": ["Which shipments were more than 24 hours late?", "Which carriers can move hazardous goods?",
                              "How much credit is Nordwerk owed for SH-4410?", "Which booked shipments have no carrier?"],
    },
    "edits": [
        ("mateo.silva", "watch_rules", "add", None, {"id": "key_account_delay", "event_type": "shipment.delayed", "when": {"path": "data.account_tier", "op": "==", "value": "Key"},
                                                    "why": "A key account shipment is running late; tell the customer before they ask", "owner_role": "Reviewer"}),
        ("mateo.silva", "kpis", "add", None, {"name": "Carrier cost per pallet", "description": "Average carrier cost", "how_to_measure": "EUR per pallet, per month"}),
    ],
    "draft_edits": [("mateo.silva", "rules", "add", None, {"id": "credit_needs_photos", "description": "Damage claims need photos", "applies_to": ["ISSUE_LATE_CREDIT"],
                                                          "condition": {"path": "hours_late", "op": ">=", "value": 0}, "on_fail": "INSUFFICIENT_EVIDENCE", "citation": "damage-claims-procedure.md p.1"})],
    "studio": {"swarm": {"agent_steps": 12}, "knowledge": {"max_rows": 500}},
    "conversations": [
        {"by": "chloe.martin", "days_ago": 18, "q": "Which shipments were more than 24 hours late?",
         "sql": "SELECT shipment_id, customer_id, hours_late, delay_cause FROM shipments WHERE hours_late > 24 ORDER BY hours_late DESC",
         "answer": "{count} shipments were more than 24 hours late:\n\n{table}\n\nOnly delays caused by the carrier earn a credit; customs and weather delays do not."},
        {"by": "piotr.nowak", "days_ago": 15, "q": "SH-4410 for Nordwerk was 52 hours late because of TransAlp. Issue the credit.",
         "search": "credit 5% per full day late", "sql": "SELECT shipment_id, freight_charge, hours_late, delay_cause FROM shipments WHERE shipment_id = 'SH-4410'",
         "answer": "SH-4410 was 52 hours late (2 full days) through the carrier's fault, so the SLA gives 10% of the 3,200 EUR charge: 320 EUR. The plan is below.",
         "plan": {"title": "Credit 320 EUR for SH-4410", "steps": [{"action": "ISSUE_LATE_CREDIT", "summary": "SLA credit, 2 days late",
                  "facts": {"shipment_id": "SH-4410", "hours_late": 52, "delay_cause": "carrier", "freight_charge": 3200, "credit_amount": 320},
                  "payload": {"shipment_id": "SH-4410", "amount": 320, "reason": "SLA: 2 days late"}}]},
         "decide": "approve", "review": ("ingrid.larsen", True, "Matches the SLA. Approved.", 14)},
        {"by": "piotr.nowak", "days_ago": 12, "q": "Vela Foods wants compensation for SH-4415, it was 30 hours late.",
         "sql": "SELECT shipment_id, hours_late, delay_cause FROM shipments WHERE shipment_id = 'SH-4415'",
         "answer": "SH-4415 was held at customs, and the SLA gives no credit for customs holds, so the rule engine blocked it.",
         "plan": {"title": "Credit for SH-4415", "steps": [{"action": "ISSUE_LATE_CREDIT", "summary": "Late credit",
                  "facts": {"shipment_id": "SH-4415", "hours_late": 30, "delay_cause": "customs", "freight_charge": 2100, "credit_amount": 105},
                  "payload": {"shipment_id": "SH-4415", "amount": 105, "reason": "Late"}}]}, "decide": "approve"},
        {"by": "lena.vogel", "days_ago": 7, "q": "Assign a carrier to SH-4446, it's hazardous.",
         "search": "hazardous ADR carrier", "sql": "SELECT carrier_id, name, safety_rating, adr_certified FROM carriers WHERE adr_certified = 1 AND contract_active = 1",
         "answer": "SH-4446 is hazardous, so it needs an ADR-certified carrier. Nordic Line (CR-4, safety 4.9) qualifies. The plan is below.",
         "plan": {"title": "Assign Nordic Line to SH-4446", "steps": [{"action": "ASSIGN_CARRIER", "summary": "ADR carrier for hazardous load",
                  "facts": {"shipment_id": "SH-4446", "carrier_id": "CR-4", "hazardous": True, "carrier_adr_certified": True, "carrier_safety_rating": 4.9},
                  "payload": {"shipment_id": "SH-4446", "carrier_id": "CR-4"}}]}, "decide": "approve"},
        {"by": "chloe.martin", "days_ago": 4, "q": "Issue the credit for SH-4427 to Atlas Pharma, 75 hours late.",
         "sql": "SELECT shipment_id, freight_charge, hours_late, delay_cause FROM shipments WHERE shipment_id = 'SH-4427'",
         "answer": "SH-4427 was 75 hours late (3 full days) through the carrier, so the SLA gives 15% of 2,750 EUR: 412.50 EUR. The plan is below for your approval.",
         "plan": {"title": "Credit 412.50 EUR for SH-4427", "steps": [{"action": "ISSUE_LATE_CREDIT", "summary": "SLA credit, 3 days late",
                  "facts": {"shipment_id": "SH-4427", "hours_late": 75, "delay_cause": "carrier", "freight_charge": 2750, "credit_amount": 412.5},
                  "payload": {"shipment_id": "SH-4427", "amount": 412.5, "reason": "SLA: 3 days late"}}]}, "decide": "approve"},
        {"by": "mateo.silva", "days_ago": 1, "q": "Which carriers can move hazardous goods?",
         "search": "ADR certified hazardous", "sql": "SELECT carrier_id, name, safety_rating FROM carriers WHERE adr_certified = 1 AND contract_active = 1",
         "answer": "{count} carriers are ADR certified with an active contract:\n\n{table}"},
    ],
    "events": [
        {"type": "shipment.delivered", "entity_id": "SH-4421", "data": {"hours_late": 0, "delay_cause": ""}, "days_ago": 16},
        {"type": "shipment.delivered", "entity_id": "SH-4442", "data": {"hours_late": 26, "delay_cause": "weather"}, "days_ago": 11},
        {"type": "shipment.booked", "entity_id": "SH-4446", "data": {"carrier_id": "", "hazardous": True}, "days_ago": 8},
        {"type": "shipment.delivered", "entity_id": "SH-4427", "data": {"hours_late": 75, "delay_cause": "carrier"}, "days_ago": 5,
         "suggest": {"title": "Issue a 412.50 EUR SLA credit to Atlas Pharma for SH-4427", "rationale": "SH-4427 arrived 75 hours late because of the carrier.",
                     "benefit": "Honours the SLA before a key account has to ask.",
                     "steps": [{"action": "ISSUE_LATE_CREDIT", "summary": "SLA credit", "facts": {"shipment_id": "SH-4427", "hours_late": 75, "delay_cause": "carrier", "freight_charge": 2750, "credit_amount": 412.5},
                                "payload": {"shipment_id": "SH-4427", "amount": 412.5, "reason": "SLA: 3 days late"}}]}},
        {"type": "shipment.delayed", "entity_id": "SH-4438", "data": {"account_tier": "Key", "eta_hours_late": 10}, "days_ago": 2},
        {"type": "shipment.picked_up", "entity_id": "SH-4433", "data": {"carrier_id": "CR-4"}, "days_ago": 3},
    ],
}

BUSINESSES = [PEAK, LUMEN, BRIGHTLINE]
