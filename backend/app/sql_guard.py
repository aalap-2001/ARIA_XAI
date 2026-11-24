"""Symbolic guard for model-written SQL. The model proposes a query; this decides whether it may run.

Rules: exactly one statement; SELECT / set operations only; no DML, DDL, SELECT INTO or dangerous
functions anywhere in the tree; every table must exist and be inside the caller's scope; a row limit
is always applied."""
import sqlglot
from sqlglot import exp

DIALECT = {"postgres": "postgres", "mysql": "mysql", "mssql": "tsql", "sqlite": "sqlite", "upload": "sqlite"}
FORBIDDEN_NODES = (exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter, exp.Command, exp.Merge,
                   exp.TruncateTable, exp.Into, exp.Transaction, exp.Commit, exp.Rollback, exp.Set, exp.Use, exp.Grant)
FORBIDDEN_FUNCS = {"pg_sleep", "sleep", "benchmark", "load_file", "pg_read_file", "pg_read_binary_file", "pg_ls_dir", "lo_import",
                   "lo_export", "dblink", "dblink_exec", "xp_cmdshell", "openrowset", "opendatasource", "load_extension",
                   "readfile", "writefile", "pg_terminate_backend", "set_config"}
MAX_ROWS = 200


class GuardError(Exception):
    pass


def guard(sql: str, kind: str, known_tables: list[str], allowed_tables: list[str], limit: int = MAX_ROWS) -> tuple[str, list[str]]:
    dialect = DIALECT.get(kind, "postgres")
    try:
        stmts = [s for s in sqlglot.parse(sql, read=dialect) if s is not None]
    except sqlglot.errors.ParseError as ex:
        raise GuardError(f"SQL could not be parsed: {str(ex).splitlines()[0][:200]}") from ex
    if len(stmts) != 1:
        raise GuardError("Exactly one SQL statement is allowed")
    stmt = stmts[0]
    if not isinstance(stmt, (exp.Select, exp.SetOperation)):
        raise GuardError(f"Only read-only SELECT queries are allowed (got {stmt.key.upper()})")
    for node in stmt.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise GuardError(f"{type(node).__name__.upper()} is not allowed in a read-only query")
        if isinstance(node, (exp.Anonymous, exp.Func)):
            fname = (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()
            if fname in FORBIDDEN_FUNCS:
                raise GuardError(f"Function {fname}() is not allowed")
    ctes = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE)}
    known = {t.lower(): t for t in known_tables}
    allowed = {t.lower() for t in allowed_tables}
    used = []
    for t in stmt.find_all(exp.Table):
        name = t.name.lower()
        if not name or name in ctes:
            continue
        if name not in known:
            raise GuardError(f"Table '{t.name}' does not exist in this connection")
        if "*" not in allowed and name not in allowed:
            raise GuardError(f"Your role is not allowed to read table '{known[name]}'")
        used.append(known[name])
    if not used:
        raise GuardError("The query must read from at least one table")
    if isinstance(stmt, exp.Select):
        cur = stmt.args.get("limit")
        n = None
        try:
            n = int(cur.expression.this) if cur is not None else None
        except (AttributeError, TypeError, ValueError):
            n = None
        if n is None or n > limit:
            stmt = stmt.limit(limit)
        safe = stmt
    else:
        safe = exp.select("*").from_(stmt.subquery("q")).limit(limit)
    return safe.sql(dialect=dialect), sorted(set(used))
