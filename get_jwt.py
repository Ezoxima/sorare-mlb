"""
get_jwt.py
-----------
Génère un JWT Sorare et le sauvegarde dans .env sous la clé SORARE_JWT.
Gère la 2FA si activée.

Usage :
    python get_jwt.py

Dépendances : bcrypt (pip install bcrypt)
"""

import getpass
import json
import os
import re
from pathlib import Path

import bcrypt
import requests
from dotenv import load_dotenv

ENV_PATH   = Path(__file__).parent / ".." / ".env"
SORARE_API = "https://api.sorare.com/graphql"

load_dotenv(dotenv_path=ENV_PATH)

AUD = "Ezox_api"


def _post(query: str, variables: dict | None = None, jwt: str | None = None) -> dict:
    headers = {"Content-Type": "application/json"}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"
    else:
        headers["APIKEY"] = os.getenv("API_KEY", "")
    resp = requests.post(SORARE_API,
                         json={"query": query, "variables": variables or {}},
                         headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _get_salt(email: str) -> str:
    resp = requests.get(f"https://api.sorare.com/api/v1/users/{email}", timeout=10)
    resp.raise_for_status()
    return resp.json()["salt"]


def _hash_password(password: str, salt: str) -> str:
    return bcrypt.hashpw(password.encode(), salt.encode()).decode()


SIGN_IN_STEP1 = """
mutation SignInStep1($input: signInInput!) {
  signIn(input: $input) {
    currentUser { slug }
    otpSessionChallenge
    errors { message }
  }
}
"""


def _mutation_with_jwt(name: str, extra_fields: str = "") -> str:
    return f"""
mutation {name}($input: signInInput!) {{
  signIn(input: $input) {{
    currentUser {{ slug }}
    jwtToken(aud: "{AUD}") {{ token expiredAt }}
    {extra_fields}
    errors {{ message }}
  }}
}}
"""


def _save_jwt(token: str):
    content = ENV_PATH.read_text(encoding="utf-8") if ENV_PATH.exists() else ""
    if "SORARE_JWT=" in content:
        content = re.sub(r"SORARE_JWT=.*", f"SORARE_JWT={token}", content)
    else:
        content = content.rstrip("\n") + f"\nSORARE_JWT={token}\n"
    ENV_PATH.write_text(content, encoding="utf-8")
    print(f"JWT sauvegardé dans {ENV_PATH}")


def main():
    email    = input("Email Sorare : ").strip()
    password = getpass.getpass("Mot de passe : ")

    print("Récupération du salt...")
    salt = _get_salt(email)

    print("Hachage du mot de passe...")
    hashed = _hash_password(password, salt)

    # Tente sans OTP d'abord
    print("Connexion...")
    data = _post(SIGN_IN_STEP1, {"input": {"email": email, "password": hashed}})
    sign_in = data.get("data", {}).get("signIn", {})
    errors  = sign_in.get("errors", [])

    needs_otp = (
        sign_in.get("otpSessionChallenge") or
        any("2fa" in (e.get("message") or "").lower() for e in errors)
    )

    if needs_otp:
        otp = input("Code 2FA (Google Authenticator) : ").strip()
        otp_challenge = sign_in.get("otpSessionChallenge")
        inp = {"email": email, "password": hashed, "otpAttempt": otp}
        if otp_challenge:
            inp["otpSessionChallenge"] = otp_challenge
        data2   = _post(_mutation_with_jwt("SignInOtp"), {"input": inp})
        sign_in = data2.get("data", {}).get("signIn", {})
        errors  = sign_in.get("errors", [])
        if errors:
            print(f"Erreur 2FA : {errors}")
            return
    elif errors:
        print(f"Erreur : {errors}")
        return
    else:
        data3   = _post(_mutation_with_jwt("SignInNoOtp", "otpSessionChallenge"),
                        {"input": {"email": email, "password": hashed}})
        sign_in = data3.get("data", {}).get("signIn", {})
        errors  = sign_in.get("errors", [])
        if errors:
            print(f"Erreur : {errors}")
            return

    jwt_data = sign_in.get("jwtToken", {})
    token    = jwt_data.get("token")
    expires  = jwt_data.get("expiredAt")

    if not token:
        print("Pas de token dans la réponse :")
        print(json.dumps(data, indent=2))
        return

    slug = sign_in.get("currentUser", {}).get("slug", "?")
    print(f"Connecté : {slug}")
    print(f"Token expire : {expires}")
    _save_jwt(token)

    # Introspection + probe currentUser fields
    print("\n── Introspection schema ──")
    intr = _post("{ __schema { types { name kind } } }", jwt=token)
    types = intr.get("data", {}).get("__schema", {}).get("types", [])
    if not types:
        print("Introspection bloquée ou vide. Réponse brute :")
        print(json.dumps(intr, indent=2, ensure_ascii=False)[:2000])
    else:
        print(f"  {len(types)} types trouvés. Pertinents :")
        for t in sorted(types, key=lambda x: x["name"]):
            if any(kw in t["name"].lower()
                   for kw in ("mission", "quest", "challenge", "objective",
                               "reward", "so5", "current")):
                print(f"  {t['kind']:12} {t['name']}")

    print("\n── Champs de CurrentUser ──")
    cu = _post('{ __type(name: "CurrentUser") { fields { name type { name kind } } } }', jwt=token)
    fields = cu.get("data", {}).get("__type", {}) or {}
    if fields.get("fields"):
        for f in fields["fields"]:
            print(f"  {f['name']:40} {f['type'].get('name') or f['type'].get('kind')}")
    else:
        print("  Pas de champs (introspection bloquée ?)")
        print(json.dumps(cu, indent=2, ensure_ascii=False)[:1000])

    print("\n── Probe so5.currentUser ──")
    probe = _post("""
    { so5 { currentSo5LeaderboardMembership { id slug } } }
    """, jwt=token)
    print(json.dumps(probe, indent=2, ensure_ascii=False)[:2000])


if __name__ == "__main__":
    main()
