# carrell_splash

The landing page at `https://carrell.us`: a card for every public site, and,
after Google sign-in, the private apps the signed-in person can use.

## Who sees what

Each site in `sites.json` has an `access` value:

| access   | Shown to |
|----------|----------|
| `public` | everyone |
| `meals`  | emails in meal_planner's `meals_alloweduser` table (checked live) |
| `vault`  | enabled accounts in Vaultwarden's `users` table (checked live) |
| `admin`  | emails listed in `ADMIN_EMAILS` |

So granting someone Meal Planner or Vault access in those apps is all it takes
for the card to show up here. `sites.json` is bind-mounted; edits apply on the
next page load.

The database checks use the read-only Postgres role `carrell_dashboard`, which
can only `SELECT` the columns it needs. One-time setup: follow the steps at the
top of `setup_role.sql` (set the password, run part 1 in `meal_planner` and
part 2 in `vault_warden`).

Connect via `192.168.68.78` (pg_hba rejects the Docker bridge address that
`host.docker.internal` resolves to). Use a hex password, or URL-encode it: an
`@` in a URL-style DSN breaks parsing.

## Environment variables (names only)

- `SECRET_KEY` — Flask session signing key
- `GOOGLE_CLIENT_ID` — OAuth web client; `https://carrell.us` must be an
  Authorized JavaScript origin
- `ADMIN_EMAILS` — comma-separated
- `MEALS_DATABASE_URL`, `VAULT_DATABASE_URL` — `postgresql://` DSNs for the
  read-only role
- `SESSION_COOKIE_SECURE` — optional, `0` for plain-http local testing

Port 8008.
