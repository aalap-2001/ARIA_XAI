"""Six synthetic businesses, one for each vertical Aria XAI serves: healthcare, financial services, industrial AI, robotics
and physical AI, property tech, and commodities and markets. Same structure as demo_data.py; everything here is invented.
"""

# ====================================================================== V.01 Healthcare
HARBOR = {
    "name": "Harbor Health Network (demo)",
    "domain": "harborhealth.example",
    "description": (
        "Harbor Health Network runs 14 outpatient clinics and two imaging centres. Front-desk staff handle patient intake, the "
        "revenue cycle team requests prior authorisations from payers before imaging and procedures, and coders turn clinical "
        "notes into claims. Payers deny claims when authorisation is missing or the billed code is higher than the documentation "
        "supports. Good looks like: no procedure without authorisation, first-pass claim acceptance above 95%, no upcoding."),
    "documents": {
        "payer-policy-advanced-imaging.md": (
            "# Payer policy: advanced imaging\n\nMRI of the lumbar spine or knee needs prior authorisation.\n\nAuthorisation is only "
            "granted after at least 6 weeks of documented conservative therapy (physiotherapy, medication or both).\n\n"
            "The request must include complete clinical documentation. Requests above 2,000 USD are reviewed by the utilisation "
            "review nurse before submission."),
        "coding-compliance-policy.md": (
            "# Coding compliance policy\n\nThe evaluation and management level billed must never be higher than the level the "
            "clinical documentation supports.\n\nCorrections are only made on claims that are open or denied, never on paid claims.\n\n"
            "Every correction is recorded with the coder's reason."),
        "patient-intake-procedure.md": (
            "# Patient intake procedure\n\nVerify insurance eligibility before the visit.\n\nCollect consent for treatment and for "
            "sharing records with the payer.\n\nPatient data is only used for the care and billing of that patient (HIPAA minimum necessary)."),
    },
    "database": {
        "name": "Practice management system",
        "tables": {
            "patients": (["patient_id", "name", "payer", "plan_type", "eligible"], [
                ("P-1001", "Maria Gonzalez", "BlueCrest", "PPO", 1), ("P-1002", "James O'Neil", "Unity Health", "HMO", 1),
                ("P-1003", "Aisha Bello", "BlueCrest", "HMO", 1), ("P-1004", "Tom Reilly", "Medicare", "Part B", 1),
                ("P-1005", "Lin Chen", "Unity Health", "PPO", 0)]),
            "orders": (["order_id", "patient_id", "procedure_code", "procedure", "payer", "estimated_cost", "weeks_conservative_therapy", "documentation_complete", "auth_status"], [
                ("ORD-2207", "P-1001", "72148", "MRI lumbar spine", "BlueCrest", 2400, 8, 1, "needed"),
                ("ORD-2211", "P-1002", "73721", "MRI knee", "Unity Health", 1900, 2, 1, "needed"),
                ("ORD-2213", "P-1003", "72148", "MRI lumbar spine", "BlueCrest", 2400, 7, 0, "needed"),
                ("ORD-2215", "P-1004", "73721", "MRI knee", "Medicare", 1750, 10, 1, "needed"),
                ("ORD-2190", "P-1005", "71046", "Chest X-ray", "Unity Health", 140, 0, 1, "not_required")]),
            "claims": (["claim_id", "patient_id", "cpt_code", "billed_level", "documented_level", "billed_amount", "status"], [
                ("CLM-9031", "P-1001", "99215", 5, 4, 310, "denied"), ("CLM-9035", "P-1002", "99213", 3, 3, 145, "paid"),
                ("CLM-9038", "P-1003", "99214", 4, 4, 220, "open"), ("CLM-9040", "P-1004", "99215", 5, 5, 310, "denied"),
                ("CLM-9042", "P-1005", "99214", 4, 3, 220, "open")]),
            "prior_auth_submissions": (["submission_id", "order_id", "payer", "estimated_cost", "justification"], [
                (501, "ORD-2150", "BlueCrest", 2400, "9 weeks of physiotherapy, persistent radicular pain")]),
        },
        "key": {"prior_auth_submissions": "submission_id"},
    },
    "people": [("Rachel Kim", "rachel.kim", "Org admin"), ("Omar Haddad", "omar.haddad", "Builder"),
               ("Elena Ruiz", "elena.ruiz", "Reviewer"), ("Sam Patel", "sam.patel", "Operator"), ("Grace Liu", "grace.liu", "Operator")],
    "content": {
        "summary": ("Harbor Health Network runs outpatient clinics and imaging centres. The agent team checks orders against payer "
                    "policy, prepares prior authorisation requests and catches coding that the documentation does not support, "
                    "with the utilisation review nurse and coding lead approving."),
        "industry": "Healthcare (outpatient care and revenue cycle)", "business_model": "Fee-for-service clinics billing commercial payers and Medicare",
        "primary_users": ["Front desk", "Revenue cycle team", "Coders", "Utilisation review nurse"],
        "ontology": [
            {"name": "Patient", "description": "A person treated at the clinics.", "source": {"connection_id": "$DB", "table": "patients"}, "key_fields": ["patient_id"], "fields": [{"name": "payer", "type": "string"}]},
            {"name": "Order", "description": "An imaging or procedure order that may need prior authorisation.", "source": {"connection_id": "$DB", "table": "orders"}, "key_fields": ["order_id"], "fields": [{"name": "estimated_cost", "type": "number"}, {"name": "weeks_conservative_therapy", "type": "number"}]},
            {"name": "Claim", "description": "A bill sent to the payer for a visit.", "source": {"connection_id": "$DB", "table": "claims"}, "key_fields": ["claim_id"], "fields": [{"name": "billed_level", "type": "number"}, {"name": "documented_level", "type": "number"}]},
            {"name": "Prior authorisation", "description": "A request sent to a payer before a procedure.", "source": {"connection_id": "$DB", "table": "prior_auth_submissions"}, "key_fields": ["submission_id"], "fields": []},
        ],
        "facts": [
            {"name": "order_id", "type": "string", "description": "The order concerned"},
            {"name": "payer", "type": "string", "description": "The patient's insurer"},
            {"name": "weeks_conservative_therapy", "type": "number", "description": "Weeks of documented conservative therapy", "unit": "weeks"},
            {"name": "documentation_complete", "type": "boolean", "description": "The clinical documentation is complete"},
            {"name": "estimated_cost", "type": "number", "description": "Estimated cost of the procedure", "unit": "USD"},
            {"name": "claim_id", "type": "string", "description": "The claim concerned"},
            {"name": "claim_status", "type": "string", "description": "open, denied or paid"},
            {"name": "new_level", "type": "number", "description": "Evaluation and management level after the correction"},
            {"name": "documented_level", "type": "number", "description": "Level the clinical documentation supports"},
            {"name": "cpt_code", "type": "string", "description": "Corrected CPT code"},
        ],
        "signals": [
            {"id": "therapy_tried", "description": "Conservative therapy was tried long enough", "combine": "weighted_sum",
             "inputs": [{"fact": "weeks_conservative_therapy", "weight": 1, "min": 0, "max": 12}], "assert_above": 0.5, "deny_below": 0.25},
        ],
        "rules": [
            {"id": "six_weeks_therapy", "description": "Imaging needs at least 6 weeks of conservative therapy", "applies_to": ["SUBMIT_PRIOR_AUTH"],
             "condition": {"path": "signals.therapy_tried", "is": True}, "on_fail": "INVALID", "message": "Less than 6 weeks of conservative therapy", "citation": "payer-policy-advanced-imaging.md p.1"},
            {"id": "documentation_complete", "description": "The request needs complete clinical documentation", "applies_to": ["SUBMIT_PRIOR_AUTH"],
             "condition": {"path": "documentation_complete", "is": True}, "on_fail": "INSUFFICIENT_EVIDENCE", "message": "Clinical documentation is incomplete", "citation": "payer-policy-advanced-imaging.md p.1"},
            {"id": "no_upcoding", "description": "Never bill above the documented level", "applies_to": ["CORRECT_CLAIM_CODE"],
             "condition": {"path": "new_level", "op": "<=", "value": "$documented_level"}, "on_fail": "INVALID", "message": "Level is higher than the documentation supports", "citation": "coding-compliance-policy.md p.1"},
            {"id": "only_open_claims", "description": "Only open or denied claims can be corrected", "applies_to": ["CORRECT_CLAIM_CODE"],
             "condition": {"path": "claim_status", "op": "in", "value": ["open", "denied"]}, "on_fail": "INVALID", "message": "The claim is already paid", "citation": "coding-compliance-policy.md p.1"},
        ],
        "actions": [
            {"name": "SUBMIT_PRIOR_AUTH", "description": "Submit a prior authorisation request to the payer", "risk": "MEDIUM", "amount_fact": "estimated_cost",
             "required_facts": ["order_id", "payer", "weeks_conservative_therapy", "documentation_complete", "estimated_cost"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "prior_auth_submissions", "operation": "insert", "columns": ["order_id", "payer", "estimated_cost", "justification"]}},
            {"name": "CORRECT_CLAIM_CODE", "description": "Correct the billed code on an open or denied claim", "risk": "LOW",
             "required_facts": ["claim_id", "claim_status", "new_level", "documented_level", "cpt_code"], "owner_role": "Org admin",
             "executor": {"type": "database", "connection_id": "$DB", "table": "claims", "operation": "update", "key_column": "claim_id", "columns": ["cpt_code", "billed_level", "status"]}},
        ],
        "watch_rules": [
            {"id": "order_needs_auth", "event_type": "order.created", "when": {"path": "data.auth_required", "op": "==", "value": True},
             "why": "A new order needs prior authorisation before the patient is booked", "owner_role": "Reviewer"},
            {"id": "claim_denied", "event_type": "claim.denied", "why": "A payer denied a claim; check whether the coding or the authorisation was the cause", "owner_role": "Org admin"},
        ],
        "agents": [
            {"id": "auth_specialist", "name": "Prior authorisation specialist", "purpose": "Checks orders against payer policy and prepares requests.",
             "instructions": "Quote the payer policy and the weeks of therapy. Never submit without complete documentation.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["orders", "patients", "prior_auth_submissions"]}], "actions": ["SUBMIT_PRIOR_AUTH"]},
            {"id": "coding_specialist", "name": "Coding specialist", "purpose": "Compares billed codes with the documented level.",
             "instructions": "Only ever lower a level to match documentation. Quote claim ids.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["claims", "patients"]}], "actions": ["CORRECT_CLAIM_CODE"]},
        ],
        "kpis": [
            {"name": "First-pass claim acceptance", "description": "Claims paid without a denial", "how_to_measure": "Share of claims, target 95%"},
            {"name": "Authorisation turnaround", "description": "Days from order to authorisation", "how_to_measure": "Median days, target under 3"},
            {"name": "Upcoding findings", "description": "Claims billed above the documentation", "how_to_measure": "Count per month, target 0"},
        ],
        "starter_questions": ["Which imaging orders still need prior authorisation?", "Which open claims are billed above the documented level?",
                              "What does BlueCrest require for a lumbar MRI?", "Submit the prior authorisation for ORD-2207."],
    },
    "edits": [("omar.haddad", "kpis", "add", None, {"name": "Denials from missing authorisation", "description": "Denials the team could have prevented", "how_to_measure": "Count per month"})],
    "draft_edits": [],
    "studio": {"interface": {"reply_length": "short"}},
    "conversations": [
        {"by": "sam.patel", "days_ago": 19, "q": "Which imaging orders still need prior authorisation?",
         "sql": "SELECT order_id, patient_id, procedure, payer, weeks_conservative_therapy FROM orders WHERE auth_status = 'needed'",
         "answer": "{count} orders still need prior authorisation:\n\n{table}\n\nOrders with less than 6 weeks of conservative therapy will not meet payer policy yet."},
        {"by": "sam.patel", "days_ago": 15, "q": "Submit the prior authorisation for ORD-2207, the lumbar MRI for Maria Gonzalez.",
         "search": "MRI lumbar spine 6 weeks conservative therapy", "sql": "SELECT order_id, payer, estimated_cost, weeks_conservative_therapy, documentation_complete FROM orders WHERE order_id = 'ORD-2207'",
         "answer": "ORD-2207 meets BlueCrest's policy: 8 weeks of conservative therapy and complete documentation. At 2,400 USD it goes to the utilisation review nurse. The plan is below.",
         "plan": {"title": "Prior authorisation for ORD-2207", "steps": [{"action": "SUBMIT_PRIOR_AUTH", "summary": "Lumbar MRI, 8 weeks of therapy",
                  "facts": {"order_id": "ORD-2207", "payer": "BlueCrest", "weeks_conservative_therapy": 8, "documentation_complete": True, "estimated_cost": 2400},
                  "payload": {"order_id": "ORD-2207", "payer": "BlueCrest", "estimated_cost": 2400, "justification": "8 weeks of physiotherapy and NSAIDs without relief"}}]},
         "decide": "approve", "review": ("elena.ruiz", True, "Documentation reviewed. Submit.", 14)},
        {"by": "grace.liu", "days_ago": 11, "q": "Send the knee MRI authorisation for ORD-2211 to Unity Health.",
         "sql": "SELECT order_id, weeks_conservative_therapy, documentation_complete FROM orders WHERE order_id = 'ORD-2211'",
         "answer": "ORD-2211 has only 2 weeks of conservative therapy, and the payer requires 6, so the rule engine blocked the request. It would be denied.",
         "plan": {"title": "Prior authorisation for ORD-2211", "steps": [{"action": "SUBMIT_PRIOR_AUTH", "summary": "Knee MRI",
                  "facts": {"order_id": "ORD-2211", "payer": "Unity Health", "weeks_conservative_therapy": 2, "documentation_complete": True, "estimated_cost": 1900},
                  "payload": {"order_id": "ORD-2211", "payer": "Unity Health", "estimated_cost": 1900, "justification": "Knee pain"}}]}, "decide": "approve"},
        {"by": "rachel.kim", "days_ago": 6, "q": "CLM-9031 was denied. Correct it to the documented level.",
         "search": "billed level never higher than documentation", "sql": "SELECT claim_id, cpt_code, billed_level, documented_level, status FROM claims WHERE claim_id = 'CLM-9031'",
         "answer": "CLM-9031 was billed at level 5 (99215) but the note supports level 4, which is why it was denied. Correcting it to 99214 is allowed because the claim is denied, not paid.",
         "plan": {"title": "Correct CLM-9031 to 99214", "steps": [{"action": "CORRECT_CLAIM_CODE", "summary": "Match the documented level",
                  "facts": {"claim_id": "CLM-9031", "claim_status": "denied", "new_level": 4, "documented_level": 4, "cpt_code": "99214"},
                  "payload": {"claim_id": "CLM-9031", "cpt_code": "99214", "billed_level": 4, "status": "open"}}]}, "decide": "approve"},
        {"by": "omar.haddad", "days_ago": 2, "q": "Which open claims are billed above the documented level?",
         "sql": "SELECT claim_id, cpt_code, billed_level, documented_level FROM claims WHERE status = 'open' AND billed_level > documented_level",
         "answer": "{count} open claim is billed above what the documentation supports:\n\n{table}\n\nCorrect it before it goes to the payer."},
    ],
    "events": [
        {"type": "patient.checked_in", "entity_id": "P-1003", "data": {"clinic": "Harbor East"}, "days_ago": 17},
        {"type": "order.created", "entity_id": "ORD-2190", "data": {"auth_required": False}, "days_ago": 13},
        {"type": "claim.denied", "entity_id": "CLM-9040", "data": {"reason": "Missing modifier"}, "days_ago": 8},
        {"type": "order.created", "entity_id": "ORD-2215", "data": {"auth_required": True, "payer": "Medicare"}, "days_ago": 3,
         "suggest": {"title": "Request prior authorisation for ORD-2215 (knee MRI, Medicare)", "rationale": "ORD-2215 needs authorisation; 10 weeks of therapy and complete documentation meet the policy.",
                     "benefit": "The patient can be booked without risking a 1,750 USD denial.",
                     "steps": [{"action": "SUBMIT_PRIOR_AUTH", "summary": "Knee MRI", "facts": {"order_id": "ORD-2215", "payer": "Medicare", "weeks_conservative_therapy": 10, "documentation_complete": True, "estimated_cost": 1750},
                                "payload": {"order_id": "ORD-2215", "payer": "Medicare", "estimated_cost": 1750, "justification": "10 weeks of physiotherapy"}}]}},
        {"type": "patient.checked_in", "entity_id": "P-1001", "data": {"clinic": "Harbor Imaging"}, "days_ago": 1},
    ],
}

# ====================================================================== V.02 Financial services
NORTHSTAR = {
    "name": "Northstar Wealth Partners (demo)",
    "domain": "northstarwealth.example",
    "description": (
        "Northstar Wealth Partners is a registered investment adviser with 1,200 client households. Advisers recommend funds and "
        "portfolios, the operations team rebalances accounts, and compliance must show that every recommendation is in the "
        "client's best interest under Regulation Best Interest: suitable for the client's risk tolerance, reasonably priced and "
        "disclosed. Good looks like: every recommendation documented, no unsuitable products, accounts within 5% of target."),
    "documents": {
        "reg-bi-care-obligation.md": (
            "# Regulation Best Interest: care obligation\n\nA recommendation must match the client's investment profile: the "
            "product's risk level may not exceed the client's risk tolerance.\n\nCost matters: when a reasonably available "
            "alternative is materially cheaper, the adviser must document why the recommended product is still in the client's "
            "best interest.\n\nRecommendations above 25,000 USD are reviewed by the chief compliance officer."),
        "rebalancing-policy.md": (
            "# Rebalancing policy\n\nAccounts are rebalanced when the equity allocation drifts 5 percentage points or more from "
            "the target.\n\nRebalancing must not create a short-term capital gain above 2,000 USD without the client's consent."),
        "client-onboarding.md": (
            "# Client onboarding\n\nEvery client completes a risk questionnaire that sets a risk tolerance from 1 (conservative) "
            "to 5 (aggressive).\n\nThe profile is reviewed every 12 months or after a life event."),
    },
    "database": {
        "name": "Portfolio and CRM system",
        "tables": {
            "clients": (["client_id", "name", "risk_tolerance", "age", "horizon_years", "last_review"], [
                ("C-101", "The Whitaker Family Trust", 3, 58, 12, "2026-02-10"), ("C-102", "Diane Foster", 2, 71, 5, "2025-09-30"),
                ("C-103", "Marcus and Jo Hale", 4, 44, 20, "2026-06-01"), ("C-104", "Priya Raman", 4, 39, 25, "2026-03-15"),
                ("C-105", "Henry Osei", 1, 80, 3, "2025-08-20")]),
            "products": (["product_id", "name", "risk_level", "annual_fee_pct", "cheaper_alternative"], [
                ("F-1", "Northstar Core Bond", 1, 0.25, 0), ("F-2", "Global Balanced Fund", 3, 0.45, 0), ("F-3", "US Total Market Index", 4, 0.05, 0),
                ("F-4", "Thematic Tech Active", 5, 1.35, 1), ("F-5", "Emerging Markets Growth", 5, 0.95, 0)]),
            "accounts": (["account_id", "client_id", "equity_pct", "target_equity_pct", "value"], [
                ("A-201", "C-101", 61, 60, 1850000), ("A-202", "C-102", 38, 30, 640000), ("A-204", "C-103", 87, 80, 920000),
                ("A-205", "C-104", 78, 80, 310000), ("A-207", "C-105", 26, 20, 410000)]),
            "recommendations": (["rec_id", "client_id", "product_id", "amount", "rationale"], [(3001, "C-101", "F-2", 40000, "Annual review: add balanced exposure")]),
        },
        "key": {"recommendations": "rec_id"},
    },
    "people": [("Jonathan Pierce", "jonathan.pierce", "Org admin"), ("Mei Tanaka", "mei.tanaka", "Builder"),
               ("Carla Mendes", "carla.mendes", "Reviewer"), ("Ben Adler", "ben.adler", "Operator"), ("Sofia Rossi", "sofia.rossi", "Operator")],
    "content": {
        "summary": ("Northstar Wealth Partners advises 1,200 households. The agent team checks every recommendation against the "
                    "client's profile and cost, prepares rebalancing, and documents the reasoning compliance needs under Reg BI."),
        "industry": "Financial services (registered investment adviser)", "business_model": "Fee-based wealth management",
        "primary_users": ["Advisers", "Operations", "Chief compliance officer"],
        "ontology": [
            {"name": "Client", "description": "A household we advise, with its risk profile.", "source": {"connection_id": "$DB", "table": "clients"}, "key_fields": ["client_id"], "fields": [{"name": "risk_tolerance", "type": "number"}]},
            {"name": "Product", "description": "A fund we can recommend.", "source": {"connection_id": "$DB", "table": "products"}, "key_fields": ["product_id"], "fields": [{"name": "risk_level", "type": "number"}, {"name": "annual_fee_pct", "type": "number"}]},
            {"name": "Account", "description": "A managed account and its allocation.", "source": {"connection_id": "$DB", "table": "accounts"}, "key_fields": ["account_id"], "fields": [{"name": "equity_pct", "type": "number"}]},
            {"name": "Recommendation", "description": "A documented recommendation to a client.", "source": {"connection_id": "$DB", "table": "recommendations"}, "key_fields": ["rec_id"], "fields": []},
        ],
        "facts": [
            {"name": "client_id", "type": "string", "description": "The client"},
            {"name": "product_id", "type": "string", "description": "The recommended product"},
            {"name": "client_risk_tolerance", "type": "number", "description": "Client risk tolerance, 1 to 5"},
            {"name": "product_risk_level", "type": "number", "description": "Product risk level, 1 to 5"},
            {"name": "annual_fee_pct", "type": "number", "description": "Product annual fee", "unit": "%"},
            {"name": "cheaper_alternative_exists", "type": "boolean", "description": "A materially cheaper similar product is available"},
            {"name": "amount", "type": "number", "description": "Amount to invest", "unit": "USD"},
            {"name": "account_id", "type": "string", "description": "The account to rebalance"},
            {"name": "drift_pct", "type": "number", "description": "Equity drift from target", "unit": "percentage points"},
            {"name": "target_equity_pct", "type": "number", "description": "Target equity allocation", "unit": "%"},
        ],
        "signals": [
            {"id": "cost_reasonable", "description": "The product's cost is reasonable", "combine": "weighted_sum",
             "inputs": [{"fact": "annual_fee_pct", "weight": 1, "min": 0, "max": 2, "invert": True}], "assert_above": 0.5, "deny_below": 0.3},
        ],
        "rules": [
            {"id": "risk_within_tolerance", "description": "Product risk may not exceed the client's risk tolerance", "applies_to": ["RECOMMEND_PRODUCT"],
             "condition": {"path": "product_risk_level", "op": "<=", "value": "$client_risk_tolerance"}, "on_fail": "INVALID", "message": "Product is riskier than the client's profile", "citation": "reg-bi-care-obligation.md p.1"},
            {"id": "cost_justified", "description": "Costly products need no cheaper alternative", "applies_to": ["RECOMMEND_PRODUCT"],
             "condition": {"any": [{"path": "signals.cost_reasonable", "is": True}, {"path": "cheaper_alternative_exists", "is": False}]}, "on_fail": "INVALID", "message": "A materially cheaper alternative exists", "citation": "reg-bi-care-obligation.md p.1"},
            {"id": "drift_five_points", "description": "Rebalance only at 5 points of drift or more", "applies_to": ["REBALANCE_ACCOUNT"],
             "condition": {"path": "drift_pct", "op": ">=", "value": 5}, "on_fail": "INVALID", "message": "Drift is below 5 percentage points", "citation": "rebalancing-policy.md p.1"},
        ],
        "actions": [
            {"name": "RECOMMEND_PRODUCT", "description": "Record a recommendation to a client", "risk": "MEDIUM", "amount_fact": "amount",
             "required_facts": ["client_id", "product_id", "client_risk_tolerance", "product_risk_level", "annual_fee_pct", "amount"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "recommendations", "operation": "insert", "columns": ["client_id", "product_id", "amount", "rationale"]}},
            {"name": "REBALANCE_ACCOUNT", "description": "Rebalance an account back to its target allocation", "risk": "LOW",
             "required_facts": ["account_id", "drift_pct", "target_equity_pct"], "owner_role": "Org admin",
             "executor": {"type": "database", "connection_id": "$DB", "table": "accounts", "operation": "update", "key_column": "account_id", "columns": ["equity_pct"]}},
        ],
        "watch_rules": [
            {"id": "allocation_drift", "event_type": "account.drift", "when": {"path": "data.drift_pct", "op": ">=", "value": 5},
             "why": "An account drifted 5 points or more from its target allocation", "owner_role": "Org admin"},
            {"id": "profile_overdue", "event_type": "client.review_due", "why": "A client profile has not been reviewed for 12 months", "owner_role": "Reviewer"},
        ],
        "agents": [
            {"id": "suitability_specialist", "name": "Suitability specialist", "purpose": "Matches products to client profiles and cost.",
             "instructions": "Compare product risk with client tolerance and check cheaper alternatives. Quote the Reg BI policy.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["clients", "products", "recommendations"]}], "actions": ["RECOMMEND_PRODUCT"]},
            {"id": "portfolio_specialist", "name": "Portfolio specialist", "purpose": "Watches allocations and prepares rebalancing.",
             "instructions": "Report drift in percentage points against the target.", "tools": ["query_data", "search_knowledge"],
             "data_scope": [{"connection_id": "$DB", "tables": ["accounts", "clients"]}], "actions": ["REBALANCE_ACCOUNT"]},
        ],
        "kpis": [
            {"name": "Recommendations documented", "description": "Recommendations with a recorded rationale", "how_to_measure": "Share, target 100%"},
            {"name": "Accounts within tolerance", "description": "Accounts within 5 points of target", "how_to_measure": "Share of accounts"},
            {"name": "Overdue profile reviews", "description": "Clients not reviewed for 12 months", "how_to_measure": "Count, target 0"},
        ],
        "starter_questions": ["Which accounts drifted more than 5 points from target?", "Which client profiles are overdue for review?",
                              "Is the Thematic Tech fund suitable for Diane Foster?", "What does Reg BI require on cost?"],
    },
    "edits": [("mei.tanaka", "watch_rules", "add", None, {"id": "large_withdrawal", "event_type": "account.withdrawal", "when": {"path": "data.amount", "op": ">", "value": 50000},
                                                     "why": "A large withdrawal may change the client's plan; the adviser should call", "owner_role": "Reviewer"})],
    "draft_edits": [],
    "studio": {"interface": {"tone": "formal"}},
    "conversations": [
        {"by": "ben.adler", "days_ago": 20, "q": "Which client profiles are overdue for review?",
         "sql": "SELECT client_id, name, last_review FROM clients WHERE last_review < '2025-11-24' ORDER BY last_review",
         "answer": "{count} client profiles have not been reviewed for 12 months:\n\n{table}\n\nReg BI expects the profile to be current before any new recommendation."},
        {"by": "ben.adler", "days_ago": 14, "q": "Recommend 50,000 USD of the US Total Market Index to Priya Raman.",
         "search": "risk level may not exceed tolerance", "sql": "SELECT c.client_id, c.risk_tolerance, p.product_id, p.risk_level, p.annual_fee_pct FROM clients c, products p WHERE c.client_id = 'C-104' AND p.product_id = 'F-3'",
         "answer": "Priya's risk tolerance is 4 and the index fund's risk level is 4, with a 0.05% fee, so it is suitable and low cost. Above 25,000 USD it goes to compliance. The plan is below.",
         "plan": {"title": "Recommend F-3 to C-104", "steps": [{"action": "RECOMMEND_PRODUCT", "summary": "Long horizon, low-cost equity",
                  "facts": {"client_id": "C-104", "product_id": "F-3", "client_risk_tolerance": 4, "product_risk_level": 4, "annual_fee_pct": 0.05, "cheaper_alternative_exists": False, "amount": 50000},
                  "payload": {"client_id": "C-104", "product_id": "F-3", "amount": 50000, "rationale": "25-year horizon, tolerance 4, lowest-cost broad equity"}}]},
         "decide": "approve", "review": ("carla.mendes", True, "Suitable and documented. Approved.", 13)},
        {"by": "sofia.rossi", "days_ago": 9, "q": "Put 30,000 USD of Diane Foster's cash into Thematic Tech Active.",
         "sql": "SELECT c.risk_tolerance, p.risk_level, p.annual_fee_pct FROM clients c, products p WHERE c.client_id = 'C-102' AND p.product_id = 'F-4'",
         "answer": "Diane's risk tolerance is 2 and Thematic Tech Active is risk level 5 with a 1.35% fee and a cheaper alternative. The rule engine blocked it: it would not be in her best interest.",
         "plan": {"title": "Recommend F-4 to C-102", "steps": [{"action": "RECOMMEND_PRODUCT", "summary": "Growth exposure",
                  "facts": {"client_id": "C-102", "product_id": "F-4", "client_risk_tolerance": 2, "product_risk_level": 5, "annual_fee_pct": 1.35, "cheaper_alternative_exists": True, "amount": 30000},
                  "payload": {"client_id": "C-102", "product_id": "F-4", "amount": 30000, "rationale": "Growth"}}]}, "decide": "approve"},
        {"by": "jonathan.pierce", "days_ago": 5, "q": "Rebalance the Hale account, it's well over target equity.",
         "search": "rebalanced when drift 5 percentage points", "sql": "SELECT account_id, equity_pct, target_equity_pct FROM accounts WHERE account_id = 'A-204'",
         "answer": "A-204 holds 87% equity against an 80% target, 7 points of drift, so the policy calls for rebalancing back to 80%.",
         "plan": {"title": "Rebalance A-204 to 80% equity", "steps": [{"action": "REBALANCE_ACCOUNT", "summary": "7 points of drift",
                  "facts": {"account_id": "A-204", "drift_pct": 7, "target_equity_pct": 80}, "payload": {"account_id": "A-204", "equity_pct": 80}}]}, "decide": "approve"},
        {"by": "mei.tanaka", "days_ago": 1, "q": "Which accounts drifted more than 5 points from target?",
         "sql": "SELECT account_id, client_id, equity_pct, target_equity_pct, equity_pct - target_equity_pct AS drift FROM accounts WHERE ABS(equity_pct - target_equity_pct) >= 5",
         "answer": "{count} accounts are 5 points or more away from target:\n\n{table}"},
    ],
    "events": [
        {"type": "account.drift", "entity_id": "A-201", "data": {"drift_pct": 1}, "days_ago": 16},
        {"type": "client.review_due", "entity_id": "C-105", "data": {"last_review": "2025-08-20"}, "days_ago": 12},
        {"type": "account.deposit", "entity_id": "A-205", "data": {"amount": 12000}, "days_ago": 7},
        {"type": "account.drift", "entity_id": "A-202", "data": {"drift_pct": 8}, "days_ago": 3,
         "suggest": {"title": "Rebalance Diane Foster's account A-202 back to 30% equity", "rationale": "A-202 is at 38% equity against a 30% target, 8 points of drift, too much risk for a tolerance of 2.",
                     "benefit": "Brings a conservative client back to her agreed risk level.",
                     "steps": [{"action": "REBALANCE_ACCOUNT", "summary": "8 points of drift", "facts": {"account_id": "A-202", "drift_pct": 8, "target_equity_pct": 30}, "payload": {"account_id": "A-202", "equity_pct": 30}}]}},
        {"type": "account.deposit", "entity_id": "A-201", "data": {"amount": 50000}, "days_ago": 1},
    ],
}

# ====================================================================== V.03 Industrial AI
IRONVALE = {
    "name": "Ironvale Manufacturing (demo)",
    "domain": "ironvale.example",
    "description": (
        "Ironvale Manufacturing makes stamped and machined steel parts for automotive customers on three production lines. "
        "Sensors report vibration and running hours for every machine; maintenance planners raise work orders, and the "
        "purchasing team reorders spare parts from approved suppliers. Process engineers want to know the happy path: the "
        "batches that ran without deviations, and why. Good looks like: no unplanned stops, scrap under 2%, parts always in stock."),
    "documents": {
        "maintenance-standard.md": (
            "# Maintenance standard\n\nRaise a maintenance work order when vibration exceeds 7 mm/s or a machine passes 1,500 "
            "running hours since its last service.\n\nWork orders above 1,000 EUR need the maintenance manager's approval.\n\n"
            "Never schedule maintenance on a line during a customer-critical run without the plant manager."),
        "purchasing-policy.md": (
            "# Purchasing policy\n\nSpare parts may only be ordered from approved suppliers with an on-time rate of at least 90%.\n\n"
            "Orders above 5,000 EUR need the purchasing lead."),
        "process-happy-path.md": (
            "# Process happy path\n\nThe happy path for line 2 is: load coil, stamp, deburr, inspect, pack, with no rework loop.\n\n"
            "Batches that follow it average a 41 minute cycle and under 1% scrap. Each rework loop adds about 9 minutes."),
    },
    "database": {
        "name": "Plant MES and ERP",
        "tables": {
            "machines": (["machine_id", "name", "line", "vibration_mm_s", "hours_since_service", "status"], [
                ("M-03", "Coil feeder", "Line 1", 2.4, 300, "running"), ("M-07", "800t press", "Line 2", 9.2, 1850, "running"),
                ("M-09", "Deburring cell", "Line 2", 5.1, 900, "running"), ("M-11", "CNC mill 4", "Line 3", 8.7, 1200, "running"),
                ("M-14", "Packing robot", "Line 3", 1.8, 1600, "running")]),
            "parts": (["part_id", "name", "stock", "reorder_level", "supplier_id", "unit_cost"], [
                ("PT-112", "Spindle bearing 6205", 4, 10, "SUP-1", 85), ("PT-118", "Hydraulic seal kit", 2, 6, "SUP-2", 140),
                ("PT-121", "Press die insert", 3, 2, "SUP-1", 620), ("PT-130", "Servo motor belt", 12, 8, "SUP-3", 45)]),
            "suppliers": (["supplier_id", "name", "on_time_pct", "approved"], [
                ("SUP-1", "Rhein Industrial Supply", 96, 1), ("SUP-2", "Fluidtec", 92, 1), ("SUP-3", "Budget Parts Direct", 78, 0)]),
            "process_runs": (["batch_id", "line", "cycle_time_min", "rework_loops", "scrap_pct"], [
                ("B-5101", "Line 2", 41, 0, 0.8), ("B-5102", "Line 2", 59, 2, 2.9), ("B-5103", "Line 2", 40, 0, 0.6),
                ("B-5104", "Line 2", 50, 1, 1.9), ("B-5105", "Line 2", 42, 0, 0.9), ("B-5106", "Line 2", 68, 3, 3.4)]),
            "work_orders": (["wo_id", "machine_id", "task", "priority", "estimated_cost"], [(7001, "M-09", "Replace deburring brushes", "normal", 420)]),
            "purchase_orders": (["po_id", "part_id", "supplier_id", "quantity", "amount"], [(8801, "PT-130", "SUP-1", 20, 900)]),
        },
        "key": {"work_orders": "wo_id", "purchase_orders": "po_id"},
    },
    "people": [("Klaus Werner", "klaus.werner", "Org admin"), ("Ana Silva", "ana.silva", "Builder"),
               ("Jakub Novak", "jakub.novak", "Reviewer"), ("Lea Fischer", "lea.fischer", "Operator"), ("Marco Bianchi", "marco.bianchi", "Operator")],
    "content": {
        "summary": ("Ironvale Manufacturing runs three steel-part production lines. The agent team reads machine telemetry and "
                    "process runs, raises maintenance before failures, reorders spare parts from approved suppliers, and explains "
                    "the happy path that keeps cycle time and scrap low."),
        "industry": "Industrial manufacturing", "business_model": "Contract manufacturing for automotive OEMs",
        "primary_users": ["Maintenance planners", "Purchasing", "Process engineers", "Plant manager"],
        "ontology": [
            {"name": "Machine", "description": "Equipment on a line with live telemetry.", "source": {"connection_id": "$DB", "table": "machines"}, "key_fields": ["machine_id"], "fields": [{"name": "vibration_mm_s", "type": "number"}, {"name": "hours_since_service", "type": "number"}]},
            {"name": "Spare part", "description": "A part kept in stock for maintenance.", "source": {"connection_id": "$DB", "table": "parts"}, "key_fields": ["part_id"], "fields": [{"name": "stock", "type": "number"}]},
            {"name": "Supplier", "description": "A company we buy parts from.", "source": {"connection_id": "$DB", "table": "suppliers"}, "key_fields": ["supplier_id"], "fields": [{"name": "on_time_pct", "type": "number"}]},
            {"name": "Process run", "description": "One production batch and how it went.", "source": {"connection_id": "$DB", "table": "process_runs"}, "key_fields": ["batch_id"], "fields": [{"name": "cycle_time_min", "type": "number"}]},
        ],
        "facts": [
            {"name": "machine_id", "type": "string", "description": "The machine concerned"},
            {"name": "vibration_mm_s", "type": "number", "description": "Measured vibration", "unit": "mm/s"},
            {"name": "hours_since_service", "type": "number", "description": "Running hours since last service", "unit": "hours"},
            {"name": "estimated_cost", "type": "number", "description": "Estimated maintenance cost", "unit": "EUR"},
            {"name": "part_id", "type": "string", "description": "Spare part to order"},
            {"name": "supplier_id", "type": "string", "description": "Supplier to order from"},
            {"name": "supplier_approved", "type": "boolean", "description": "The supplier is on the approved list"},
            {"name": "supplier_on_time_pct", "type": "number", "description": "Supplier on-time delivery rate", "unit": "%"},
            {"name": "quantity", "type": "number", "description": "Quantity to order"},
            {"name": "amount", "type": "number", "description": "Order value", "unit": "EUR"},
        ],
        "signals": [
            {"id": "failure_risk", "description": "The machine is at risk of failing", "combine": "noisy_or",
             "inputs": [{"fact": "vibration_mm_s", "weight": 0.9, "min": 4, "max": 9}, {"fact": "hours_since_service", "weight": 0.8, "min": 800, "max": 1800}],
             "assert_above": 0.6, "deny_below": 0.3},
        ],
        "rules": [
            {"id": "maintenance_needed", "description": "Maintenance only when vibration or running hours show a real risk", "applies_to": ["CREATE_WORK_ORDER"],
             "condition": {"path": "signals.failure_risk", "is": True}, "on_fail": "INVALID", "message": "Telemetry shows no failure risk yet", "citation": "maintenance-standard.md p.1"},
            {"id": "approved_supplier", "description": "Only approved suppliers", "applies_to": ["REORDER_PART"],
             "condition": {"path": "supplier_approved", "is": True}, "on_fail": "INVALID", "message": "Supplier is not approved", "citation": "purchasing-policy.md p.1"},
            {"id": "supplier_on_time", "description": "Supplier on-time rate of at least 90%", "applies_to": ["REORDER_PART"],
             "condition": {"path": "supplier_on_time_pct", "op": ">=", "value": 90}, "on_fail": "INVALID", "message": "Supplier on-time rate below 90%", "citation": "purchasing-policy.md p.1"},
        ],
        "actions": [
            {"name": "CREATE_WORK_ORDER", "description": "Raise a maintenance work order for a machine", "risk": "MEDIUM", "amount_fact": "estimated_cost",
             "required_facts": ["machine_id", "vibration_mm_s", "hours_since_service", "estimated_cost"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "work_orders", "operation": "insert", "columns": ["machine_id", "task", "priority", "estimated_cost"]}},
            {"name": "REORDER_PART", "description": "Order spare parts from a supplier", "risk": "LOW", "amount_fact": "amount",
             "required_facts": ["part_id", "supplier_id", "supplier_approved", "supplier_on_time_pct", "quantity", "amount"], "owner_role": "Org admin",
             "executor": {"type": "database", "connection_id": "$DB", "table": "purchase_orders", "operation": "insert", "columns": ["part_id", "supplier_id", "quantity", "amount"]}},
        ],
        "watch_rules": [
            {"id": "vibration_high", "event_type": "machine.telemetry", "when": {"path": "data.vibration_mm_s", "op": ">", "value": 7},
             "why": "A machine is vibrating above 7 mm/s; it may fail during a run", "owner_role": "Reviewer"},
            {"id": "part_low", "event_type": "part.stock_low", "why": "A spare part fell below its reorder level", "owner_role": "Org admin"},
        ],
        "agents": [
            {"id": "maintenance_specialist", "name": "Maintenance specialist", "purpose": "Reads telemetry and plans maintenance.",
             "instructions": "Quote vibration in mm/s and hours since service.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["machines", "work_orders"]}], "actions": ["CREATE_WORK_ORDER"]},
            {"id": "process_specialist", "name": "Process mining specialist", "purpose": "Finds the happy path and what slows batches down.",
             "instructions": "Compare batches with and without rework loops.", "tools": ["query_data", "search_knowledge"],
             "data_scope": [{"connection_id": "$DB", "tables": ["process_runs"]}], "actions": []},
            {"id": "purchasing_specialist", "name": "Purchasing specialist", "purpose": "Keeps spare parts in stock from approved suppliers.",
             "instructions": "Check approval and on-time rate before ordering.", "tools": ["query_data", "search_knowledge"],
             "data_scope": [{"connection_id": "$DB", "tables": ["parts", "suppliers", "purchase_orders"]}], "actions": ["REORDER_PART"]},
        ],
        "kpis": [
            {"name": "Unplanned stops", "description": "Stops not caused by planned maintenance", "how_to_measure": "Count per month, target 0"},
            {"name": "Scrap rate", "description": "Share of parts scrapped", "how_to_measure": "Per line, target under 2%"},
            {"name": "Happy-path share", "description": "Batches without a rework loop", "how_to_measure": "Share of batches"},
        ],
        "starter_questions": ["Which machines vibrate above 7 mm/s?", "What is the happy path on line 2 and what does a rework loop cost?",
                              "Which spare parts are below their reorder level?", "Raise maintenance for the 800t press."],
    },
    "edits": [("ana.silva", "kpis", "add", None, {"name": "Mean time between failures", "description": "Hours between breakdowns", "how_to_measure": "Per machine"})],
    "draft_edits": [],
    "studio": {"swarm": {"agent_steps": 12}},
    "conversations": [
        {"by": "lea.fischer", "days_ago": 18, "q": "Which machines vibrate above 7 mm/s?",
         "sql": "SELECT machine_id, name, line, vibration_mm_s, hours_since_service FROM machines WHERE vibration_mm_s > 7",
         "answer": "{count} machines are above the 7 mm/s threshold:\n\n{table}\n\nBoth meet the maintenance standard for a work order.", "agent": "maintenance_specialist"},
        {"by": "lea.fischer", "days_ago": 15, "q": "Raise a maintenance work order for the 800t press M-07.",
         "search": "vibration exceeds 7 mm/s 1,500 running hours", "sql": "SELECT machine_id, vibration_mm_s, hours_since_service FROM machines WHERE machine_id = 'M-07'",
         "answer": "M-07 runs at 9.2 mm/s with 1,850 hours since service, a clear failure risk. The work order is estimated at 1,800 EUR, so the maintenance manager approves it. The plan is below.",
         "plan": {"title": "Maintenance for M-07", "steps": [{"action": "CREATE_WORK_ORDER", "summary": "Bearing and alignment check",
                  "facts": {"machine_id": "M-07", "vibration_mm_s": 9.2, "hours_since_service": 1850, "estimated_cost": 1800},
                  "payload": {"machine_id": "M-07", "task": "Replace main bearing, check alignment", "priority": "high", "estimated_cost": 1800}}]},
         "decide": "approve", "review": ("jakub.novak", True, "Schedule it for the Saturday shift.", 14)},
        {"by": "marco.bianchi", "days_ago": 10, "q": "Service the coil feeder M-03 this week.",
         "sql": "SELECT machine_id, vibration_mm_s, hours_since_service FROM machines WHERE machine_id = 'M-03'",
         "answer": "M-03 runs at 2.4 mm/s with 300 hours since service, well inside limits, so the rule engine blocked the work order. Servicing it now would only cost line time.",
         "plan": {"title": "Maintenance for M-03", "steps": [{"action": "CREATE_WORK_ORDER", "summary": "Routine service",
                  "facts": {"machine_id": "M-03", "vibration_mm_s": 2.4, "hours_since_service": 300, "estimated_cost": 600},
                  "payload": {"machine_id": "M-03", "task": "Routine service", "priority": "normal", "estimated_cost": 600}}]}, "decide": "approve"},
        {"by": "klaus.werner", "days_ago": 6, "q": "Spindle bearings are low. Reorder 20 from Rhein Industrial.",
         "search": "approved suppliers on-time rate 90%", "sql": "SELECT p.part_id, p.stock, p.reorder_level, s.on_time_pct, s.approved FROM parts p JOIN suppliers s ON s.supplier_id = 'SUP-1' WHERE p.part_id = 'PT-112'",
         "answer": "PT-112 is at 4 against a reorder level of 10. Rhein Industrial is approved with a 96% on-time rate, so 20 bearings at 85 EUR (1,700 EUR) can be ordered.",
         "plan": {"title": "Reorder 20 x PT-112", "steps": [{"action": "REORDER_PART", "summary": "Below reorder level",
                  "facts": {"part_id": "PT-112", "supplier_id": "SUP-1", "supplier_approved": True, "supplier_on_time_pct": 96, "quantity": 20, "amount": 1700},
                  "payload": {"part_id": "PT-112", "supplier_id": "SUP-1", "quantity": 20, "amount": 1700}}]}, "decide": "approve"},
        {"by": "ana.silva", "days_ago": 2, "q": "What is the happy path on line 2 and what does a rework loop cost?", "agent": "process_specialist",
         "search": "happy path line 2 rework loop", "sql": "SELECT rework_loops, COUNT(*) AS batches, ROUND(AVG(cycle_time_min), 1) AS avg_cycle_min, ROUND(AVG(scrap_pct), 2) AS avg_scrap_pct FROM process_runs GROUP BY rework_loops ORDER BY rework_loops",
         "answer": "The happy path is load, stamp, deburr, inspect, pack with no rework. By number of rework loops:\n\n{table}\n\nEach loop adds roughly 9 minutes and about 1 point of scrap, so preventing the first rework matters most."},
    ],
    "events": [
        {"type": "machine.telemetry", "entity_id": "M-14", "data": {"vibration_mm_s": 1.8}, "days_ago": 16},
        {"type": "batch.completed", "entity_id": "B-5105", "data": {"cycle_time_min": 42, "rework_loops": 0}, "days_ago": 9},
        {"type": "part.stock_low", "entity_id": "PT-118", "data": {"stock": 2, "reorder_level": 6}, "days_ago": 5,
         "suggest": {"title": "Reorder 8 hydraulic seal kits PT-118 from Fluidtec", "rationale": "PT-118 is at 2 against a reorder level of 6; Fluidtec is approved with 92% on time.",
                     "benefit": "Avoids waiting for seals if a press leaks.",
                     "steps": [{"action": "REORDER_PART", "summary": "Below reorder level", "facts": {"part_id": "PT-118", "supplier_id": "SUP-2", "supplier_approved": True, "supplier_on_time_pct": 92, "quantity": 8, "amount": 1120},
                                "payload": {"part_id": "PT-118", "supplier_id": "SUP-2", "quantity": 8, "amount": 1120}}], "decide": ("klaus.werner", True, 4)}},
        {"type": "machine.telemetry", "entity_id": "M-11", "data": {"vibration_mm_s": 8.7}, "days_ago": 2,
         "suggest": {"title": "Raise maintenance for CNC mill M-11 (8.7 mm/s)", "rationale": "M-11 vibrates at 8.7 mm/s, above the 7 mm/s limit, with 1,200 hours since service.",
                     "benefit": "Prevents an unplanned stop on line 3.",
                     "steps": [{"action": "CREATE_WORK_ORDER", "summary": "Spindle inspection", "facts": {"machine_id": "M-11", "vibration_mm_s": 8.7, "hours_since_service": 1200, "estimated_cost": 950},
                                "payload": {"machine_id": "M-11", "task": "Inspect spindle bearings", "priority": "high", "estimated_cost": 950}}]}},
        {"type": "batch.completed", "entity_id": "B-5106", "data": {"cycle_time_min": 68, "rework_loops": 3}, "days_ago": 1},
    ],
}

# ====================================================================== V.04 Robotics and physical AI
KINETIQ = {
    "name": "Kinetiq Robotics (demo)",
    "domain": "kinetiq.example",
    "description": (
        "Kinetiq Robotics operates a fleet of 40 autonomous mobile robots in a customer's fulfilment centre. Robots pick, carry "
        "and replenish across zones where people also work. The fleet team dispatches missions, the safety officer decides how "
        "much autonomy each robot gets, and every near-miss is logged. Good looks like: no injuries, missions completed first "
        "time, robots never in restricted zones and never sent out on a low battery."),
    "documents": {
        "bounded-autonomy-policy.md": (
            "# Bounded autonomy policy\n\nAutonomy levels: 1 tele-operated, 2 supervised, 3 autonomous in marked zones, 4 fully "
            "autonomous.\n\nA robot may only be raised to a higher level after 30 days without an incident. Lowering a level is "
            "always allowed.\n\nLevel changes are approved by the safety officer."),
        "mission-dispatch-rules.md": (
            "# Mission dispatch rules\n\nDo not dispatch a robot below 30% battery.\n\nPayload may not exceed the robot's rated "
            "maximum.\n\nRobots never enter restricted zones (cold store, chemicals) without a human escort."),
        "incident-procedure.md": (
            "# Incident procedure\n\nEvery collision or near-miss is logged with a severity from 1 to 3.\n\nAfter a severity 2 or 3 "
            "incident the robot is lowered to autonomy level 1 until reviewed."),
    },
    "database": {
        "name": "Fleet management system",
        "tables": {
            "robots": (["robot_id", "model", "zone", "battery_pct", "max_payload_kg", "autonomy_level", "incidents_30d", "status"], [
                ("R-02", "AMR-500", "A", 91, 500, 2, 0, "idle"), ("R-04", "AMR-300", "B", 18, 300, 3, 1, "charging"),
                ("R-07", "AMR-500", "B", 82, 500, 3, 0, "idle"), ("R-09", "AMR-300", "D", 64, 300, 3, 0, "on_mission"),
                ("R-12", "AMR-1000", "A", 47, 1000, 2, 0, "idle")]),
            "zones": (["zone", "name", "restricted", "humans_present", "max_speed_mps"], [
                ("A", "Inbound dock", 0, 1, 1.2), ("B", "Pick aisles", 0, 1, 1.5), ("C", "Cold store", 1, 0, 0.8), ("D", "Outbound", 0, 0, 2.0)]),
            "incidents": (["incident_id", "robot_id", "type", "severity", "days_ago"], [
                ("INC-31", "R-04", "near-miss with forklift", 2, 6), ("INC-29", "R-09", "pallet clipped", 1, 41)]),
            "missions": (["mission_id", "robot_id", "task", "zone", "payload_kg"], [(9001, "R-09", "Move 12 totes to outbound", "D", 180)]),
        },
        "key": {"missions": "mission_id"},
    },
    "people": [("Nadia Haas", "nadia.haas", "Org admin"), ("Leo Martins", "leo.martins", "Builder"),
               ("Victor Hale", "victor.hale", "Reviewer"), ("Ivy Brooks", "ivy.brooks", "Operator"), ("Kenji Sato", "kenji.sato", "Operator")],
    "content": {
        "summary": ("Kinetiq Robotics runs an autonomous mobile robot fleet in a fulfilment centre. The agent team plans missions "
                    "within battery, payload and zone limits, and keeps every robot's autonomy bounded by its safety record."),
        "industry": "Robotics and physical AI", "business_model": "Robots-as-a-service for warehouses",
        "primary_users": ["Fleet operators", "Safety officer", "Site manager"],
        "ontology": [
            {"name": "Robot", "description": "A mobile robot with battery, payload and autonomy level.", "source": {"connection_id": "$DB", "table": "robots"}, "key_fields": ["robot_id"], "fields": [{"name": "battery_pct", "type": "number"}, {"name": "autonomy_level", "type": "number"}]},
            {"name": "Zone", "description": "An area of the building and its safety limits.", "source": {"connection_id": "$DB", "table": "zones"}, "key_fields": ["zone"], "fields": [{"name": "restricted", "type": "boolean"}]},
            {"name": "Incident", "description": "A collision or near-miss.", "source": {"connection_id": "$DB", "table": "incidents"}, "key_fields": ["incident_id"], "fields": [{"name": "severity", "type": "number"}]},
            {"name": "Mission", "description": "A task given to a robot.", "source": {"connection_id": "$DB", "table": "missions"}, "key_fields": ["mission_id"], "fields": []},
        ],
        "facts": [
            {"name": "robot_id", "type": "string", "description": "The robot concerned"},
            {"name": "battery_pct", "type": "number", "description": "Battery charge", "unit": "%"},
            {"name": "payload_kg", "type": "number", "description": "Payload for the mission", "unit": "kg"},
            {"name": "max_payload_kg", "type": "number", "description": "Robot's rated payload", "unit": "kg"},
            {"name": "zone_restricted", "type": "boolean", "description": "The mission zone is restricted"},
            {"name": "zone", "type": "string", "description": "Zone of the mission"},
            {"name": "current_autonomy_level", "type": "number", "description": "Autonomy level now, 1 to 4"},
            {"name": "target_autonomy_level", "type": "number", "description": "Autonomy level requested, 1 to 4"},
            {"name": "incidents_30d", "type": "number", "description": "Incidents in the last 30 days"},
        ],
        "signals": [
            {"id": "battery_ready", "description": "The battery is charged enough for a mission", "combine": "weighted_sum",
             "inputs": [{"fact": "battery_pct", "weight": 1, "min": 0, "max": 100}], "assert_above": 0.3, "deny_below": 0.2},
        ],
        "rules": [
            {"id": "battery_30", "description": "No missions below 30% battery", "applies_to": ["DISPATCH_MISSION"],
             "condition": {"path": "signals.battery_ready", "is": True}, "on_fail": "INVALID", "message": "Battery below 30%", "citation": "mission-dispatch-rules.md p.1"},
            {"id": "payload_limit", "description": "Payload within the robot's rating", "applies_to": ["DISPATCH_MISSION"],
             "condition": {"path": "payload_kg", "op": "<=", "value": "$max_payload_kg"}, "on_fail": "INVALID", "message": "Payload above the robot's rating", "citation": "mission-dispatch-rules.md p.1"},
            {"id": "no_restricted_zone", "description": "Never into a restricted zone without escort", "applies_to": ["DISPATCH_MISSION"],
             "condition": {"path": "zone_restricted", "is": False}, "on_fail": "INVALID", "message": "Zone is restricted", "citation": "mission-dispatch-rules.md p.1"},
            {"id": "earn_autonomy", "description": "Raise autonomy only after 30 incident-free days; lowering is always allowed", "applies_to": ["SET_AUTONOMY_LEVEL"],
             "condition": {"any": [{"path": "target_autonomy_level", "op": "<=", "value": "$current_autonomy_level"}, {"path": "incidents_30d", "op": "<=", "value": 0}]},
             "on_fail": "INVALID", "message": "The robot had an incident in the last 30 days", "citation": "bounded-autonomy-policy.md p.1"},
        ],
        "actions": [
            {"name": "DISPATCH_MISSION", "description": "Send a robot on a mission", "risk": "LOW",
             "required_facts": ["robot_id", "battery_pct", "payload_kg", "max_payload_kg", "zone_restricted", "zone"], "owner_role": "Org admin",
             "executor": {"type": "database", "connection_id": "$DB", "table": "missions", "operation": "insert", "columns": ["robot_id", "task", "zone", "payload_kg"]}},
            {"name": "SET_AUTONOMY_LEVEL", "description": "Change how autonomously a robot may operate", "risk": "HIGH",
             "required_facts": ["robot_id", "current_autonomy_level", "target_autonomy_level", "incidents_30d"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "robots", "operation": "update", "key_column": "robot_id", "columns": ["autonomy_level"]}},
        ],
        "watch_rules": [
            {"id": "serious_incident", "event_type": "robot.incident", "when": {"path": "data.severity", "op": ">=", "value": 2},
             "why": "A severity 2 or 3 incident: the robot should drop to autonomy level 1", "owner_role": "Reviewer"},
            {"id": "battery_critical", "event_type": "robot.battery", "when": {"path": "data.battery_pct", "op": "<", "value": 15},
             "why": "A robot is close to stalling on the floor", "owner_role": "Org admin"},
        ],
        "agents": [
            {"id": "fleet_specialist", "name": "Fleet specialist", "purpose": "Plans missions within battery, payload and zone limits.",
             "instructions": "Check battery, payload and zone before proposing a mission.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["robots", "zones", "missions"]}], "actions": ["DISPATCH_MISSION"]},
            {"id": "safety_specialist", "name": "Safety specialist", "purpose": "Keeps autonomy bounded by each robot's safety record.",
             "instructions": "Quote incidents and the bounded autonomy policy.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["robots", "incidents"]}], "actions": ["SET_AUTONOMY_LEVEL"]},
        ],
        "kpis": [
            {"name": "Incident-free days", "description": "Days without a collision or near-miss", "how_to_measure": "Rolling count"},
            {"name": "First-time mission success", "description": "Missions completed without intervention", "how_to_measure": "Share, target 98%"},
            {"name": "Fleet availability", "description": "Robots ready for work", "how_to_measure": "Share of fleet hours"},
        ],
        "starter_questions": ["Which robots are below 30% battery?", "Which zones have people working in them?",
                              "Can R-07 move 400 kg to outbound?", "Why was R-04's autonomy lowered?"],
    },
    "edits": [("leo.martins", "starter_questions", "add", None, "Which robots are eligible for a higher autonomy level?")],
    "draft_edits": [],
    "studio": {},
    "conversations": [
        {"by": "ivy.brooks", "days_ago": 17, "q": "Which robots are below 30% battery?",
         "sql": "SELECT robot_id, model, zone, battery_pct, status FROM robots WHERE battery_pct < 30",
         "answer": "{count} robot is below 30% and must not be dispatched:\n\n{table}", "agent": "fleet_specialist"},
        {"by": "nadia.haas", "days_ago": 13, "q": "Send R-07 to move 400 kg of returns from the pick aisles to outbound.",
         "search": "battery 30% payload restricted zones", "sql": "SELECT r.robot_id, r.battery_pct, r.max_payload_kg, z.restricted FROM robots r, zones z WHERE r.robot_id = 'R-07' AND z.zone = 'D'",
         "answer": "R-07 is at 82% battery, rated for 500 kg, and outbound is not restricted, so the mission is within limits.",
         "plan": {"title": "Dispatch R-07 to outbound", "steps": [{"action": "DISPATCH_MISSION", "summary": "400 kg of returns",
                  "facts": {"robot_id": "R-07", "battery_pct": 82, "payload_kg": 400, "max_payload_kg": 500, "zone_restricted": False, "zone": "D"},
                  "payload": {"robot_id": "R-07", "task": "Move returns to outbound", "zone": "D", "payload_kg": 400}}]}, "decide": "approve"},
        {"by": "kenji.sato", "days_ago": 9, "q": "Send R-04 to the cold store to fetch 2 pallets.",
         "sql": "SELECT r.robot_id, r.battery_pct, z.restricted FROM robots r, zones z WHERE r.robot_id = 'R-04' AND z.zone = 'C'",
         "answer": "R-04 is at 18% battery and the cold store is a restricted zone, so the rule engine blocked the mission on both counts.",
         "plan": {"title": "Dispatch R-04 to cold store", "steps": [{"action": "DISPATCH_MISSION", "summary": "Fetch pallets",
                  "facts": {"robot_id": "R-04", "battery_pct": 18, "payload_kg": 250, "max_payload_kg": 300, "zone_restricted": True, "zone": "C"},
                  "payload": {"robot_id": "R-04", "task": "Fetch pallets", "zone": "C", "payload_kg": 250}}]}, "decide": "approve"},
        {"by": "victor.hale", "days_ago": 6, "q": "R-04 had a near-miss with a forklift. Drop it to autonomy level 1.", "agent": "safety_specialist",
         "search": "severity 2 lowered to autonomy level 1", "sql": "SELECT robot_id, autonomy_level, incidents_30d FROM robots WHERE robot_id = 'R-04'",
         "answer": "INC-31 was severity 2, so the incident procedure lowers R-04 to level 1 until reviewed. Lowering is always allowed.",
         "plan": {"title": "Lower R-04 to autonomy level 1", "steps": [{"action": "SET_AUTONOMY_LEVEL", "summary": "After INC-31",
                  "facts": {"robot_id": "R-04", "current_autonomy_level": 3, "target_autonomy_level": 1, "incidents_30d": 1},
                  "payload": {"robot_id": "R-04", "autonomy_level": 1}}]}, "decide": "approve"},
        {"by": "leo.martins", "days_ago": 1, "q": "Which zones have people working in them?",
         "sql": "SELECT zone, name, restricted, max_speed_mps FROM zones WHERE humans_present = 1",
         "answer": "{count} zones have people working in them, and robots slow down there:\n\n{table}"},
    ],
    "events": [
        {"type": "robot.heartbeat", "entity_id": "R-12", "data": {"battery_pct": 47}, "days_ago": 15},
        {"type": "robot.incident", "entity_id": "R-09", "data": {"severity": 1, "type": "tote dropped"}, "days_ago": 11},
        {"type": "robot.incident", "entity_id": "R-04", "data": {"severity": 2, "type": "near-miss with forklift"}, "days_ago": 6},
        {"type": "robot.battery", "entity_id": "R-12", "data": {"battery_pct": 11}, "days_ago": 2,
         "suggest": {"title": "Send R-12 to charge, then finish its replenishment run", "rationale": "R-12 is at 11% battery in the inbound dock, close to stalling where people work.",
                     "benefit": "Avoids a robot blocking the dock with a dead battery.",
                     "steps": [{"action": "DISPATCH_MISSION", "summary": "Return to charger", "facts": {"robot_id": "R-12", "battery_pct": 31, "payload_kg": 0, "max_payload_kg": 1000, "zone_restricted": False, "zone": "A"},
                                "payload": {"robot_id": "R-12", "task": "Return to charger A", "zone": "A", "payload_kg": 0}}]}},
        {"type": "robot.heartbeat", "entity_id": "R-02", "data": {"battery_pct": 91}, "days_ago": 1},
    ],
}

# ====================================================================== V.05 Property tech
CEDARLINE = {
    "name": "Cedarline Residential (demo)",
    "domain": "cedarline.example",
    "description": (
        "Cedarline Residential manages 2,400 apartments in 18 buildings. Leasing agents screen applicants, the maintenance team "
        "dispatches vendors, and property managers send renewal offers. Every screening decision must follow Fair Housing law: "
        "the same objective criteria for everyone, voucher income counted like any other income, and no decision based on a "
        "protected characteristic. Good looks like: 95% occupancy, emergency repairs within 4 hours, lawful and consistent screening."),
    "documents": {
        "fair-housing-screening-policy.md": (
            "# Fair Housing screening policy\n\nEvery applicant is screened on the same two criteria only: monthly income of at "
            "least 2.5 times the rent, and a credit score of at least 620.\n\nHousing vouchers and other assistance count as income.\n\n"
            "Race, colour, religion, sex, national origin, familial status and disability are never considered."),
        "renewal-policy.md": (
            "# Renewal policy\n\nRenewal offers go out 60 days before the lease ends.\n\nRent increases at renewal are capped at 5% "
            "per year under the local stabilisation ordinance."),
        "maintenance-sla.md": (
            "# Maintenance SLA\n\nEmergencies (no heat, active leak, no water) are attended within 4 hours.\n\nOnly licensed and "
            "insured vendors may be dispatched."),
    },
    "database": {
        "name": "Property management system",
        "tables": {
            "units": (["unit_id", "building", "bedrooms", "rent", "status"], [
                ("U-2A", "Cedar Court", 2, 1850, "occupied"), ("U-4B", "Cedar Court", 1, 1450, "occupied"), ("U-7C", "Maple House", 3, 2600, "vacant"),
                ("U-9D", "Maple House", 2, 1900, "vacant"), ("U-3F", "Birch Point", 1, 1500, "occupied")]),
            "applicants": (["applicant_id", "name", "unit_id", "monthly_income", "voucher_income", "credit_score", "status"], [
                ("AP-31", "Jordan Ellis", "U-9D", 5900, 0, 690, "pending"), ("AP-33", "Fatima Noor", "U-7C", 4300, 2400, 655, "pending"),
                ("AP-35", "Chris Doyle", "U-9D", 3800, 0, 710, "pending")]),
            "leases": (["lease_id", "unit_id", "tenant", "rent", "end_date", "renewal_rent"], [
                ("L-12", "U-2A", "Hannah Weiss", 1850, "2027-01-31", None), ("L-15", "U-4B", "Daniel Park", 1450, "2027-01-15", None),
                ("L-18", "U-3F", "Rosa Alvarez", 1500, "2027-02-28", None)]),
            "vendors": (["vendor_id", "name", "trade", "licensed"], [("V-1", "AllFlow Plumbing", "plumbing", 1), ("V-2", "Handy Harry", "general", 0), ("V-3", "WarmHome HVAC", "heating", 1)]),
            "maintenance_requests": (["request_id", "unit_id", "issue", "priority", "vendor_id"], [(4401, "U-3F", "Dripping tap", "normal", "V-1")]),
        },
        "key": {"maintenance_requests": "request_id"},
    },
    "people": [("Monica Reyes", "monica.reyes", "Org admin"), ("Tyler Grant", "tyler.grant", "Builder"),
               ("Denise Okoro", "denise.okoro", "Reviewer"), ("Alex Rivera", "alex.rivera", "Operator"), ("Nina Brooks", "nina.brooks", "Operator")],
    "content": {
        "summary": ("Cedarline Residential manages 2,400 apartments. The agent team screens applicants on the same objective "
                    "criteria for everyone, prepares renewals within the rent cap, and dispatches licensed vendors for repairs."),
        "industry": "Property technology (residential property management)", "business_model": "Fee-based management of rental buildings",
        "primary_users": ["Leasing agents", "Property managers", "Maintenance coordinators"],
        "ontology": [
            {"name": "Unit", "description": "An apartment and its rent.", "source": {"connection_id": "$DB", "table": "units"}, "key_fields": ["unit_id"], "fields": [{"name": "rent", "type": "number"}]},
            {"name": "Applicant", "description": "Someone applying to rent a unit.", "source": {"connection_id": "$DB", "table": "applicants"}, "key_fields": ["applicant_id"], "fields": [{"name": "monthly_income", "type": "number"}, {"name": "credit_score", "type": "number"}]},
            {"name": "Lease", "description": "A tenancy and its renewal.", "source": {"connection_id": "$DB", "table": "leases"}, "key_fields": ["lease_id"], "fields": [{"name": "rent", "type": "number"}]},
            {"name": "Maintenance request", "description": "A repair and the vendor sent.", "source": {"connection_id": "$DB", "table": "maintenance_requests"}, "key_fields": ["request_id"], "fields": []},
        ],
        "facts": [
            {"name": "applicant_id", "type": "string", "description": "The applicant"},
            {"name": "income_to_rent_ratio", "type": "number", "description": "Monthly income including vouchers, divided by rent"},
            {"name": "credit_score", "type": "number", "description": "Applicant credit score"},
            {"name": "lease_id", "type": "string", "description": "The lease to renew"},
            {"name": "current_rent", "type": "number", "description": "Rent now", "unit": "USD"},
            {"name": "renewal_rent", "type": "number", "description": "Proposed renewal rent", "unit": "USD"},
            {"name": "increase_pct", "type": "number", "description": "Rent increase at renewal", "unit": "%"},
            {"name": "unit_id", "type": "string", "description": "The unit"},
            {"name": "vendor_id", "type": "string", "description": "Vendor to dispatch"},
            {"name": "vendor_licensed", "type": "boolean", "description": "The vendor is licensed and insured"},
        ],
        "signals": [
            {"id": "affordability", "description": "The applicant can afford the rent", "combine": "weighted_sum",
             "inputs": [{"fact": "income_to_rent_ratio", "weight": 1, "min": 0, "max": 5}], "assert_above": 0.5, "deny_below": 0.4},
        ],
        "rules": [
            {"id": "income_2_5x", "description": "Income (vouchers included) at least 2.5 times the rent", "applies_to": ["APPROVE_APPLICATION"],
             "condition": {"path": "signals.affordability", "is": True}, "on_fail": "INVALID", "message": "Income below 2.5 times the rent", "citation": "fair-housing-screening-policy.md p.1"},
            {"id": "credit_620", "description": "Credit score of at least 620", "applies_to": ["APPROVE_APPLICATION"],
             "condition": {"path": "credit_score", "op": ">=", "value": 620}, "on_fail": "INVALID", "message": "Credit score below 620", "citation": "fair-housing-screening-policy.md p.1"},
            {"id": "renewal_cap_5", "description": "Renewal increases capped at 5%", "applies_to": ["OFFER_RENEWAL"],
             "condition": {"path": "increase_pct", "op": "<=", "value": 5}, "on_fail": "INVALID", "message": "Increase above the 5% cap", "citation": "renewal-policy.md p.1"},
            {"id": "licensed_vendor", "description": "Only licensed and insured vendors", "applies_to": ["DISPATCH_VENDOR"],
             "condition": {"path": "vendor_licensed", "is": True}, "on_fail": "INVALID", "message": "Vendor is not licensed", "citation": "maintenance-sla.md p.1"},
        ],
        "actions": [
            {"name": "APPROVE_APPLICATION", "description": "Approve a rental application", "risk": "MEDIUM",
             "required_facts": ["applicant_id", "income_to_rent_ratio", "credit_score"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "applicants", "operation": "update", "key_column": "applicant_id", "columns": ["status"]}},
            {"name": "OFFER_RENEWAL", "description": "Send a renewal offer with the new rent", "risk": "MEDIUM", "amount_fact": "renewal_rent",
             "required_facts": ["lease_id", "current_rent", "renewal_rent", "increase_pct"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "leases", "operation": "update", "key_column": "lease_id", "columns": ["renewal_rent"]}},
            {"name": "DISPATCH_VENDOR", "description": "Send a vendor to a repair", "risk": "LOW",
             "required_facts": ["unit_id", "vendor_id", "vendor_licensed"], "owner_role": "Org admin",
             "executor": {"type": "database", "connection_id": "$DB", "table": "maintenance_requests", "operation": "insert", "columns": ["unit_id", "issue", "priority", "vendor_id"]}},
        ],
        "watch_rules": [
            {"id": "emergency_repair", "event_type": "maintenance.reported", "when": {"path": "data.priority", "op": "==", "value": "emergency"},
             "why": "An emergency repair must be attended within 4 hours", "owner_role": "Org admin"},
            {"id": "lease_expiring", "event_type": "lease.expiring", "when": {"path": "data.days_left", "op": "<=", "value": 60},
             "why": "A lease ends within 60 days and needs a renewal offer", "owner_role": "Reviewer"},
        ],
        "agents": [
            {"id": "leasing_specialist", "name": "Leasing specialist", "purpose": "Screens applicants on the same objective criteria for everyone.",
             "instructions": "Use only income (vouchers included) and credit score. Never mention or use protected characteristics.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["applicants", "units"]}], "actions": ["APPROVE_APPLICATION"]},
            {"id": "renewals_specialist", "name": "Renewals specialist", "purpose": "Prepares renewal offers within the rent cap.",
             "instructions": "Quote the current rent and the percentage increase.", "tools": ["query_data", "search_knowledge"],
             "data_scope": [{"connection_id": "$DB", "tables": ["leases", "units"]}], "actions": ["OFFER_RENEWAL"]},
            {"id": "maintenance_coordinator", "name": "Maintenance coordinator", "purpose": "Dispatches licensed vendors to repairs.",
             "instructions": "Emergencies first; only licensed vendors.", "tools": ["query_data", "search_knowledge"],
             "data_scope": [{"connection_id": "$DB", "tables": ["maintenance_requests", "vendors", "units"]}], "actions": ["DISPATCH_VENDOR"]},
        ],
        "kpis": [
            {"name": "Occupancy", "description": "Share of units let", "how_to_measure": "Target 95%"},
            {"name": "Emergency response time", "description": "Hours to attend an emergency", "how_to_measure": "Median, target under 4"},
            {"name": "Screening consistency", "description": "Decisions that followed the written criteria", "how_to_measure": "Share, target 100%"},
        ],
        "starter_questions": ["Which units are vacant?", "Does Fatima Noor's application meet the criteria?",
                              "Which leases end in the next 60 days?", "Which vendors can we send to a leak?"],
    },
    "edits": [("tyler.grant", "kpis", "add", None, {"name": "Renewal acceptance", "description": "Tenants who accept their renewal", "how_to_measure": "Share of offers"})],
    "draft_edits": [],
    "studio": {"interface": {"tone": "friendly"}},
    "conversations": [
        {"by": "alex.rivera", "days_ago": 18, "q": "Which units are vacant?",
         "sql": "SELECT unit_id, building, bedrooms, rent FROM units WHERE status = 'vacant'",
         "answer": "{count} units are vacant:\n\n{table}"},
        {"by": "monica.reyes", "days_ago": 12, "q": "Approve Fatima Noor's application for U-7C.", "agent": "leasing_specialist",
         "search": "vouchers count as income 2.5 times", "sql": "SELECT a.applicant_id, a.monthly_income, a.voucher_income, a.credit_score, u.rent FROM applicants a JOIN units u ON u.unit_id = a.unit_id WHERE a.applicant_id = 'AP-33'",
         "answer": "With the voucher counted as income, Fatima's monthly income is 6,700 USD against a 2,600 USD rent, a ratio of 2.58, and her credit score is 655. She meets both criteria.",
         "plan": {"title": "Approve AP-33 for U-7C", "steps": [{"action": "APPROVE_APPLICATION", "summary": "Meets income and credit criteria",
                  "facts": {"applicant_id": "AP-33", "income_to_rent_ratio": 2.58, "credit_score": 655},
                  "payload": {"applicant_id": "AP-33", "status": "approved"}}]}, "decide": "approve"},
        {"by": "nina.brooks", "days_ago": 8, "q": "Offer Hannah Weiss a renewal at 2,020 USD.", "agent": "renewals_specialist",
         "search": "rent increases capped at 5%", "sql": "SELECT lease_id, rent, end_date FROM leases WHERE lease_id = 'L-12'",
         "answer": "2,020 USD would be a 9.2% increase on 1,850 USD, above the 5% cap, so the rule engine blocked it. The highest lawful offer is 1,942 USD.",
         "plan": {"title": "Renewal for L-12 at 2,020 USD", "steps": [{"action": "OFFER_RENEWAL", "summary": "Renewal offer",
                  "facts": {"lease_id": "L-12", "current_rent": 1850, "renewal_rent": 2020, "increase_pct": 9.2},
                  "payload": {"lease_id": "L-12", "renewal_rent": 2020}}]}, "decide": "approve"},
        {"by": "monica.reyes", "days_ago": 4, "q": "Send a plumber to U-4B, the kitchen pipe is leaking.", "agent": "maintenance_coordinator",
         "sql": "SELECT vendor_id, name, licensed FROM vendors WHERE trade = 'plumbing'",
         "answer": "AllFlow Plumbing (V-1) is licensed and insured, so it can go now as an emergency.",
         "plan": {"title": "Dispatch AllFlow to U-4B", "steps": [{"action": "DISPATCH_VENDOR", "summary": "Active leak",
                  "facts": {"unit_id": "U-4B", "vendor_id": "V-1", "vendor_licensed": True},
                  "payload": {"unit_id": "U-4B", "issue": "Kitchen pipe leaking", "priority": "emergency", "vendor_id": "V-1"}}]}, "decide": "approve"},
        {"by": "tyler.grant", "days_ago": 1, "q": "Which leases end in the next 60 days?",
         "sql": "SELECT lease_id, unit_id, tenant, rent, end_date FROM leases WHERE end_date <= '2027-01-31' ORDER BY end_date",
         "answer": "{count} leases end soon and need a renewal offer:\n\n{table}"},
    ],
    "events": [
        {"type": "application.submitted", "entity_id": "AP-35", "data": {"unit_id": "U-9D"}, "days_ago": 14},
        {"type": "maintenance.reported", "entity_id": "U-3F", "data": {"priority": "normal", "issue": "Dripping tap"}, "days_ago": 10},
        {"type": "lease.expiring", "entity_id": "L-15", "data": {"days_left": 55, "rent": 1450}, "days_ago": 6,
         "suggest": {"title": "Offer Daniel Park a renewal at 1,515 USD (4.5%)", "rationale": "L-15 ends in 55 days; 4.5% stays inside the 5% cap and in line with the building.",
                     "benefit": "Keeps a good tenant and avoids a vacancy.",
                     "steps": [{"action": "OFFER_RENEWAL", "summary": "Renewal within the cap", "facts": {"lease_id": "L-15", "current_rent": 1450, "renewal_rent": 1515, "increase_pct": 4.5},
                                "payload": {"lease_id": "L-15", "renewal_rent": 1515}}]}},
        {"type": "maintenance.reported", "entity_id": "U-2A", "data": {"priority": "emergency", "issue": "No heat"}, "days_ago": 2,
         "suggest": {"title": "Dispatch WarmHome HVAC to U-2A (no heat)", "rationale": "No heat is an emergency with a 4 hour SLA; WarmHome is licensed for heating.",
                     "benefit": "Meets the emergency SLA in winter.",
                     "steps": [{"action": "DISPATCH_VENDOR", "summary": "Emergency heating repair", "facts": {"unit_id": "U-2A", "vendor_id": "V-3", "vendor_licensed": True},
                                "payload": {"unit_id": "U-2A", "issue": "No heat", "priority": "emergency", "vendor_id": "V-3"}}], "decide": ("monica.reyes", True, 2)}},
        {"type": "application.submitted", "entity_id": "AP-31", "data": {"unit_id": "U-9D"}, "days_ago": 1},
    ],
}

# ====================================================================== V.06 Commodities and markets
ATLAS = {
    "name": "Atlas Commodities Trading (demo)",
    "domain": "atlascommodities.example",
    "description": (
        "Atlas Commodities Trading buys and sells grain and base metals with about 60 counterparties worldwide. Traders book "
        "trades, the risk desk keeps each counterparty within its credit limit, and compliance screens every counterparty "
        "against sanctions lists before any deal. Every decision must be explainable to auditors. Good looks like: no sanctioned "
        "counterparty ever traded, exposure always within limits, prices close to market."),
    "documents": {
        "sanctions-screening-policy.md": (
            "# Sanctions screening policy\n\nNo trade may be booked with a counterparty that has an open sanctions hit, or whose "
            "KYC is not approved.\n\nScreening is repeated before every trade and whenever a sanctions list changes."),
        "credit-risk-policy.md": (
            "# Credit risk policy\n\nExposure to a counterparty after a trade may not exceed its credit limit.\n\nTrades above "
            "1,000,000 USD notional are approved by the head of risk.\n\nCredit limit increases need two years of trading history."),
        "pricing-policy.md": (
            "# Pricing policy\n\nTrade prices should be within 3% of the reference market price. Larger deviations need a written "
            "reason from the trader."),
    },
    "database": {
        "name": "Trading and risk system",
        "tables": {
            "counterparties": (["cp_id", "name", "country", "kyc_status", "sanctions_hit", "credit_limit", "exposure", "years_trading"], [
                ("CP-01", "Danube Grain AG", "AT", "approved", 0, 5000000, 3100000, 6), ("CP-02", "Pampas Agro SA", "AR", "approved", 0, 4000000, 1500000, 4),
                ("CP-03", "Baltic Metals Oy", "FI", "approved", 0, 2000000, 1950000, 3), ("CP-05", "Caspian Ventures Ltd", "CY", "approved", 1, 3000000, 0, 1),
                ("CP-07", "Meridia Trading FZE", "AE", "pending", 0, 1000000, 0, 0)]),
            "market_prices": (["commodity", "reference_price_usd_mt"], [("wheat", 248), ("corn", 196), ("copper", 9150), ("aluminium", 2380)]),
            "contracts": (["contract_id", "cp_id", "commodity", "quantity_mt", "price_usd_mt", "delivery_month", "status"], [
                ("CT-301", "CP-01", "wheat", 12000, 251, "2026-12", "open"), ("CT-305", "CP-03", "copper", 200, 9100, "2027-01", "open"),
                ("CT-309", "CP-02", "corn", 8000, 194, "2026-12", "delivered")]),
            "trades": (["trade_id", "cp_id", "commodity", "side", "quantity_mt", "price_usd_mt", "notional"], [(60001, "CP-01", "wheat", "buy", 4000, 247, 988000)]),
        },
        "key": {"trades": "trade_id"},
    },
    "people": [("Henrik Dahl", "henrik.dahl", "Org admin"), ("Zara Ahmed", "zara.ahmed", "Builder"),
               ("Olivia Grant", "olivia.grant", "Reviewer"), ("Lucas Moreau", "lucas.moreau", "Operator"), ("Ravi Shah", "ravi.shah", "Operator")],
    "content": {
        "summary": ("Atlas Commodities Trading deals grain and base metals with about 60 counterparties. The agent team reasons "
                    "across counterparties, sanctions, credit limits and contracts before any trade, and keeps every decision "
                    "traceable for auditors."),
        "industry": "Commodities trading", "business_model": "Physical commodity merchant (grain and base metals)",
        "primary_users": ["Traders", "Risk desk", "Compliance"],
        "ontology": [
            {"name": "Counterparty", "description": "A company we trade with, its KYC, sanctions status and credit.", "source": {"connection_id": "$DB", "table": "counterparties"}, "key_fields": ["cp_id"], "fields": [{"name": "credit_limit", "type": "number"}, {"name": "exposure", "type": "number"}]},
            {"name": "Contract", "description": "A forward delivery contract.", "source": {"connection_id": "$DB", "table": "contracts"}, "key_fields": ["contract_id"], "fields": [{"name": "quantity_mt", "type": "number"}]},
            {"name": "Market price", "description": "Reference price per tonne.", "source": {"connection_id": "$DB", "table": "market_prices"}, "key_fields": ["commodity"], "fields": [{"name": "reference_price_usd_mt", "type": "number"}]},
            {"name": "Trade", "description": "A booked purchase or sale.", "source": {"connection_id": "$DB", "table": "trades"}, "key_fields": ["trade_id"], "fields": [{"name": "notional", "type": "number"}]},
        ],
        "facts": [
            {"name": "cp_id", "type": "string", "description": "The counterparty"},
            {"name": "kyc_status", "type": "string", "description": "approved, pending or rejected"},
            {"name": "sanctions_hit", "type": "boolean", "description": "The counterparty has an open sanctions hit"},
            {"name": "post_trade_exposure", "type": "number", "description": "Exposure after the trade", "unit": "USD"},
            {"name": "credit_limit", "type": "number", "description": "Counterparty credit limit", "unit": "USD"},
            {"name": "price_deviation_pct", "type": "number", "description": "Distance of the trade price from the reference price", "unit": "%"},
            {"name": "notional", "type": "number", "description": "Trade value", "unit": "USD"},
            {"name": "commodity", "type": "string", "description": "What is traded"},
            {"name": "new_credit_limit", "type": "number", "description": "Proposed credit limit", "unit": "USD"},
            {"name": "years_trading", "type": "number", "description": "Years of trading history with us"},
        ],
        "signals": [
            {"id": "price_fair", "description": "The trade price is close to market", "combine": "weighted_sum",
             "inputs": [{"fact": "price_deviation_pct", "weight": 1, "min": 0, "max": 10, "invert": True}], "assert_above": 0.7, "deny_below": 0.5},
        ],
        "rules": [
            {"id": "no_sanctions", "description": "Never trade with a sanctioned counterparty", "applies_to": ["BOOK_TRADE"],
             "condition": {"path": "sanctions_hit", "is": False}, "on_fail": "INVALID", "message": "Open sanctions hit", "citation": "sanctions-screening-policy.md p.1"},
            {"id": "kyc_approved", "description": "KYC must be approved", "applies_to": ["BOOK_TRADE"],
             "condition": {"path": "kyc_status", "op": "in", "value": ["approved"]}, "on_fail": "INVALID", "message": "KYC not approved", "citation": "sanctions-screening-policy.md p.1"},
            {"id": "within_credit_limit", "description": "Exposure after the trade within the credit limit", "applies_to": ["BOOK_TRADE"],
             "condition": {"path": "post_trade_exposure", "op": "<=", "value": "$credit_limit"}, "on_fail": "INVALID", "message": "Trade would breach the credit limit", "citation": "credit-risk-policy.md p.1"},
            {"id": "price_near_market", "description": "Price within 3% of market", "applies_to": ["BOOK_TRADE"],
             "condition": {"path": "signals.price_fair", "is": True}, "on_fail": "INSUFFICIENT_EVIDENCE", "message": "Price far from market; the trader must explain", "citation": "pricing-policy.md p.1"},
            {"id": "history_for_limit", "description": "Credit limit increases need two years of history", "applies_to": ["SET_CREDIT_LIMIT"],
             "condition": {"path": "years_trading", "op": ">=", "value": 2}, "on_fail": "INVALID", "message": "Less than two years of history", "citation": "credit-risk-policy.md p.1"},
        ],
        "actions": [
            {"name": "BOOK_TRADE", "description": "Book a purchase or sale with a counterparty", "risk": "MEDIUM", "amount_fact": "notional",
             "required_facts": ["cp_id", "kyc_status", "sanctions_hit", "post_trade_exposure", "credit_limit", "price_deviation_pct", "notional", "commodity"], "owner_role": "Reviewer",
             "executor": {"type": "database", "connection_id": "$DB", "table": "trades", "operation": "insert", "columns": ["cp_id", "commodity", "side", "quantity_mt", "price_usd_mt", "notional"]}},
            {"name": "SET_CREDIT_LIMIT", "description": "Change a counterparty's credit limit", "risk": "MEDIUM",
             "required_facts": ["cp_id", "credit_limit", "new_credit_limit", "years_trading"], "owner_role": "Org admin",
             "executor": {"type": "database", "connection_id": "$DB", "table": "counterparties", "operation": "update", "key_column": "cp_id", "columns": ["credit_limit"]}},
        ],
        "watch_rules": [
            {"id": "sanctions_change", "event_type": "counterparty.screened", "when": {"path": "data.sanctions_hit", "op": "==", "value": True},
             "why": "A counterparty now has a sanctions hit; open contracts must be reviewed", "owner_role": "Reviewer"},
            {"id": "limit_near", "event_type": "exposure.updated", "when": {"path": "data.utilisation_pct", "op": ">=", "value": 90},
             "why": "A counterparty is using 90% or more of its credit limit", "owner_role": "Org admin"},
        ],
        "agents": [
            {"id": "counterparty_specialist", "name": "Counterparty specialist", "purpose": "Screens counterparties for sanctions, KYC and credit.",
             "instructions": "Always state sanctions status, KYC and exposure against limit.", "tools": ["query_data", "search_knowledge", "check_rules"],
             "data_scope": [{"connection_id": "$DB", "tables": ["counterparties", "trades"]}], "actions": ["BOOK_TRADE", "SET_CREDIT_LIMIT"]},
            {"id": "market_specialist", "name": "Market specialist", "purpose": "Compares prices with the market and tracks contracts.",
             "instructions": "Quote the reference price and the deviation in %.", "tools": ["query_data", "search_knowledge"],
             "data_scope": [{"connection_id": "$DB", "tables": ["market_prices", "contracts"]}], "actions": []},
        ],
        "kpis": [
            {"name": "Sanctions breaches", "description": "Trades with sanctioned counterparties", "how_to_measure": "Count, target 0"},
            {"name": "Limit utilisation", "description": "Exposure as a share of credit limits", "how_to_measure": "Per counterparty, alert at 90%"},
            {"name": "Price deviation", "description": "Average distance from the market price", "how_to_measure": "%, target under 1%"},
        ],
        "starter_questions": ["Which counterparties are above 90% of their credit limit?", "Can we buy 5,000 t of wheat from Pampas Agro at 250?",
                              "Which counterparties are not cleared to trade?", "Which contracts deliver in December?"],
    },
    "edits": [("zara.ahmed", "watch_rules", "add", None, {"id": "contract_due", "event_type": "contract.delivery_due", "why": "A contract is due for delivery; confirm logistics", "owner_role": "Reviewer"})],
    "draft_edits": [],
    "studio": {"interface": {"tone": "formal", "reply_length": "short"}},
    "conversations": [
        {"by": "ravi.shah", "days_ago": 20, "q": "Which counterparties are not cleared to trade?", "agent": "counterparty_specialist",
         "sql": "SELECT cp_id, name, kyc_status, sanctions_hit FROM counterparties WHERE kyc_status <> 'approved' OR sanctions_hit = 1",
         "answer": "{count} counterparties cannot be traded with today:\n\n{table}\n\nEither KYC is not approved or there is an open sanctions hit."},
        {"by": "lucas.moreau", "days_ago": 14, "q": "Buy 5,000 t of wheat from Pampas Agro at 250 USD per tonne.",
         "search": "exposure after trade credit limit 1,000,000", "sql": "SELECT c.cp_id, c.kyc_status, c.sanctions_hit, c.credit_limit, c.exposure, m.reference_price_usd_mt FROM counterparties c, market_prices m WHERE c.cp_id = 'CP-02' AND m.commodity = 'wheat'",
         "answer": "Pampas Agro is KYC approved with no sanctions hit. 5,000 t at 250 is 1,250,000 USD, taking exposure to 2,750,000 against a 4,000,000 limit. The price is 0.8% above market. Above 1,000,000 USD the head of risk approves.",
         "plan": {"title": "Buy 5,000 t wheat from CP-02", "steps": [{"action": "BOOK_TRADE", "summary": "Wheat purchase",
                  "facts": {"cp_id": "CP-02", "kyc_status": "approved", "sanctions_hit": False, "post_trade_exposure": 2750000, "credit_limit": 4000000, "price_deviation_pct": 0.8, "notional": 1250000, "commodity": "wheat"},
                  "payload": {"cp_id": "CP-02", "commodity": "wheat", "side": "buy", "quantity_mt": 5000, "price_usd_mt": 250, "notional": 1250000}}]},
         "decide": "approve", "review": ("olivia.grant", True, "Within limit and near market. Approved.", 13)},
        {"by": "ravi.shah", "days_ago": 10, "q": "Sell 300 t of aluminium to Caspian Ventures at 2,400.",
         "sql": "SELECT cp_id, name, kyc_status, sanctions_hit FROM counterparties WHERE cp_id = 'CP-05'",
         "answer": "Caspian Ventures has an open sanctions hit, so the rule engine blocked the trade. It cannot be booked under any circumstances.",
         "plan": {"title": "Sell 300 t aluminium to CP-05", "steps": [{"action": "BOOK_TRADE", "summary": "Aluminium sale",
                  "facts": {"cp_id": "CP-05", "kyc_status": "approved", "sanctions_hit": True, "post_trade_exposure": 720000, "credit_limit": 3000000, "price_deviation_pct": 0.8, "notional": 720000, "commodity": "aluminium"},
                  "payload": {"cp_id": "CP-05", "commodity": "aluminium", "side": "sell", "quantity_mt": 300, "price_usd_mt": 2400, "notional": 720000}}]}, "decide": "approve"},
        {"by": "henrik.dahl", "days_ago": 5, "q": "Raise Danube Grain's credit limit to 6 million.", "agent": "counterparty_specialist",
         "search": "credit limit increases two years", "sql": "SELECT cp_id, credit_limit, exposure, years_trading FROM counterparties WHERE cp_id = 'CP-01'",
         "answer": "Danube Grain has 6 years of history with us and uses 3.1 of its 5 million limit, so an increase to 6 million meets the policy.",
         "plan": {"title": "Credit limit 6,000,000 USD for CP-01", "steps": [{"action": "SET_CREDIT_LIMIT", "summary": "Long-standing counterparty",
                  "facts": {"cp_id": "CP-01", "credit_limit": 5000000, "new_credit_limit": 6000000, "years_trading": 6},
                  "payload": {"cp_id": "CP-01", "credit_limit": 6000000}}]}, "decide": "approve"},
        {"by": "zara.ahmed", "days_ago": 1, "q": "Which counterparties are above 90% of their credit limit?",
         "sql": "SELECT cp_id, name, exposure, credit_limit, ROUND(100.0 * exposure / credit_limit, 1) AS utilisation_pct FROM counterparties WHERE exposure >= 0.9 * credit_limit",
         "answer": "{count} counterparty is above 90% of its limit:\n\n{table}\n\nNew trades with it would breach the limit."},
    ],
    "events": [
        {"type": "exposure.updated", "entity_id": "CP-02", "data": {"utilisation_pct": 38}, "days_ago": 16},
        {"type": "counterparty.screened", "entity_id": "CP-01", "data": {"sanctions_hit": False}, "days_ago": 12},
        {"type": "counterparty.screened", "entity_id": "CP-05", "data": {"sanctions_hit": True, "list": "EU consolidated list"}, "days_ago": 11},
        {"type": "exposure.updated", "entity_id": "CP-03", "data": {"utilisation_pct": 97.5}, "days_ago": 3,
         "suggest": {"title": "Sell back 50 t of copper to Baltic Metals to bring exposure under 90%", "rationale": "Baltic Metals is at 97.5% of its 2,000,000 USD limit; any further delivery would breach it.",
                     "benefit": "Restores headroom with a key metals counterparty.",
                     "steps": [{"action": "BOOK_TRADE", "summary": "Reduce exposure", "facts": {"cp_id": "CP-03", "kyc_status": "approved", "sanctions_hit": False, "post_trade_exposure": 1495000, "credit_limit": 2000000, "price_deviation_pct": 0.5, "notional": 455000, "commodity": "copper"},
                                "payload": {"cp_id": "CP-03", "commodity": "copper", "side": "sell", "quantity_mt": 50, "price_usd_mt": 9100, "notional": 455000}}]}},
        {"type": "contract.delivery_due", "entity_id": "CT-301", "data": {"delivery_month": "2026-12"}, "days_ago": 1},
    ],
}

VERTICALS = [HARBOR, NORTHSTAR, IRONVALE, KINETIQ, CEDARLINE, ATLAS]

PERSONAS = {
    HARBOR["name"]: {"persona_name": "Ava", "persona_role": "patient access and billing coordinator", "avatar": "teal",
                     "traits": "caring, precise, discreet, clear", "greeting": "Hello, I'm Ava from Harbor Health. I can help with authorisations, coding questions and patient intake."},
    NORTHSTAR["name"]: {"persona_name": "Elliot", "persona_role": "client service associate", "avatar": "indigo",
                        "traits": "measured, transparent, client-first, precise", "greeting": "Good day, I'm Elliot from Northstar. I can check suitability, allocations and anything about your accounts."},
    IRONVALE["name"]: {"persona_name": "Rhea", "persona_role": "plant operations assistant", "avatar": "slate",
                       "traits": "practical, direct, safety-minded, data-driven", "greeting": "Hi, I'm Rhea. Ask me about machine health, spare parts or why a batch ran slow."},
    KINETIQ["name"]: {"persona_name": "Kit", "persona_role": "fleet operations guide", "avatar": "amber",
                      "traits": "alert, calm, safety-first, concise", "greeting": "Hi, I'm Kit. I can plan missions, check robot readiness and explain any safety decision."},
    CEDARLINE["name"]: {"persona_name": "Maya", "persona_role": "leasing and resident services guide", "avatar": "rose",
                        "traits": "welcoming, fair, helpful, consistent", "greeting": "Hi, I'm Maya from Cedarline. Looking for an apartment, a repair or help with your lease?"},
    ATLAS["name"]: {"persona_name": "Theo", "persona_role": "trading desk assistant", "avatar": "slate",
                    "traits": "rigorous, concise, compliant, numbers-first", "greeting": "Hello, I'm Theo. Ask me about counterparties, limits, sanctions status or market prices."},
}
