"""Aria XAI, domain-agnostic AI infrastructure for agentic products.

Four subsystems, one pattern: a generic engine with no domain vocabulary, reading
versioned declarative artifacts (domain bundles) with no logic, with enforcement
located outside the code being governed.

    connectors , how the system reaches data and tools
    fabric     , how the system remembers (Knowledge Fabric: short + long term)
    rules      , how the system reasons and validates (soft → gate → hard)
    sentinel   , how the system is constrained and audited
"""
__version__ = "1.0.0"
