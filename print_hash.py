import getpass, bcrypt, requests

email    = input("Email : ").strip()
password = getpass.getpass("Mot de passe : ")

salt = requests.get(f"https://api.sorare.com/api/v1/users/{email}", timeout=10).json()["salt"]
hashed = bcrypt.hashpw(password.encode(), salt.encode()).decode()

print(f"\nhashed_password : {hashed}")
