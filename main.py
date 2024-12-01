from enum import Enum
import sys
import re
import os
import winreg
import win32cred      # pywin32
import win32timezone  # pywin32
import json
import sqlite3



#  /$$      /$$           /$$ /$$
# | $$$    /$$$          |__/| $$
# | $$$$  /$$$$  /$$$$$$  /$$| $$
# | $$ $$/$$ $$ |____  $$| $$| $$
# | $$  $$$| $$  /$$$$$$$| $$| $$
# | $$\  $ | $$ /$$__  $$| $$| $$
# | $$ \/  | $$|  $$$$$$$| $$| $$
# |__/     |__/ \_______/|__/|__/

# Helpers
def addMail(mails, mail):
  # Fix mail
  mail = str(mail).replace('\r', '')

  # Not a mail -> Return
  if (not isMail(mail)):
    return
  
  # Add to dictionary
  if mail in mails:
    mails[mail] += 1
  else:
    mails[mail] = 1

def isMail(mail):
  pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
  return pattern.match(str(mail))

# Search functions
class SearchMode(Enum):
  Fast = 0
  Complete = 1

def findMail(mode):
  # Create mails dictionary
  mails = {}

  # Look for mails in registry
  findMailRegistry(mails)
  if (mode == SearchMode.Fast and len(mails) > 0): 
    return mails

  # Look for mails in windows credentials
  findMailCredentials(mails)
  if (mode == SearchMode.Fast and len(mails) > 0): 
    return mails
  
  # Look for mails in chromium browsers
  findMailChromium(mails)
  return mails

def findMailRegistry(mails):
  # Registry path & array to store mails (subkeys)
  path = 'Software\\Microsoft\\IdentityCRL\\UserExtendedProperties'
  folders = []

  # Search the key path subkeys
  try:
    # Open the registry key
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, winreg.KEY_READ)
    
    # Add all folders to list
    i = 0
    while True:
      try:
        # Get next folder & add it to the list
        subkey = winreg.EnumKey(key, i)
        folders.append(subkey)
        i += 1
      except OSError:
        # No more folders
        break

    # Close the key
    winreg.CloseKey(key)

  except FileNotFoundError:
    # Key does not exist
    print("Registry key or value not found")

  except PermissionError:
    # Missing permission to open
    print("Missing permission to read this key")

  # Create dictionary with valid mails
  for mail in folders:
    addMail(mails, mail)

def findMailCredentials(mails):
  # Look for mails in windows credentials
  try:
    # Retrieve all credentials
    credentials = win32cred.CredEnumerate(None, 0)
    
    # Has credentials -> Loop to find mail
    if credentials:
      for cred in credentials:
        mail = cred.get('UserName', 'N/A')
        addMail(mails, mail)
    else:
      print("No credentials found.")

  except Exception as e:
    # Error
    print(f"Error while reading credentials: {e}")

def findMailChromium(mails):
  # Get appdata folders
  local = os.getenv('LOCALAPPDATA')
  roaming = os.getenv('APPDATA')

  # Add mails from all known chromium browsers
  findMailChromiumFromPath(mails, local + '\\Google\\Chrome\\User Data\\')
  findMailChromiumFromPath(mails, local + '\\Microsoft\\Edge\\User Data\\')
  findMailChromiumFromPath(mails, local + '\\BraveSoftware\\Brave-Browser\\User Data\\')
  findMailChromiumFromPath(mails, roaming + '\\Opera Software\\Opera Stable\\User Data\\')
  findMailChromiumFromPath(mails, roaming + '\\Opera Software\\Opera GX Stable\\User Data\\')

def findMailChromiumFromPath(mails, path):
  # Find mail in chromium browser
  localState = path + 'Local State'

  # Check if local state file exists
  if (not os.path.exists(localState)): return

  # Read local state file
  try:
    with open(localState) as f:
      # Parse local state data (json)
      localStateData = json.load(f)
      profile = localStateData['profile']

      # Get profile names & data
      profileNames = profile['profiles_order']
      profilesData = profile['info_cache']
      
      # Loop each profile
      for name in profileNames:
        # Get profile data
        profileData = profilesData[name]

        # Get profile user name (mail)
        mail = profileData['user_name']
        addMail(mails, mail)

        # Get profile folder
        profileFolder = path + name + '\\'

        # Read preferences file
        try:
          with open(profileFolder + 'Preferences') as f:
            # Parse preferences data (json)
            preferences = json.load(f)

            # Get accounts info
            accounts = preferences['account_info']

            # Find mails in accounts
            for account in accounts:
              mail = account['email']
              addMail(mails, mail)

        except Exception as e:
          # Error
          print(f'Error reading preferences file: {e}')

        # Read login data file
        try:
          # Connect to database
          database = profileFolder + 'Login Data'
          connection = sqlite3.connect(f'file:{database}?mode=ro&immutable=1', uri = True)

          # Select logins
          cursor = connection.cursor()
          cursor.execute('SELECT username_value FROM logins')
          
          # Loop usernames & save mails
          for row in cursor.fetchall():
            addMail(mails, row[0])

          # Close database
          connection.close()

        except Exception as e:
          # Error
          print(f'Error reading login data file: {e}')
        
  except Exception as e:
    # Error
    print(f'Error finding chromium profiles: {e}')



#  /$$      /$$           /$$          
# | $$$    /$$$          |__/          
# | $$$$  /$$$$  /$$$$$$  /$$ /$$$$$$$ 
# | $$ $$/$$ $$ |____  $$| $$| $$__  $$
# | $$  $$$| $$  /$$$$$$$| $$| $$  \ $$
# | $$\  $ | $$ /$$__  $$| $$| $$  | $$
# | $$ \/  | $$|  $$$$$$$| $$| $$  | $$
# |__/     |__/ \_______/|__/|__/  |__/

# Save modes
class SaveFormat(Enum):
  JSON = 0
  Text = 1

# Get arguments & default modes
args = sys.argv
searchMode = SearchMode.Complete
saveFormat = SaveFormat.JSON

# Check arguments
for i, arg in enumerate(args):
  # Ignore first argument (file path)
  if (i == 0): 
    continue

  # Check if argument is to change a var
  if (not re.compile(r".+=.+").match(arg)):
    continue

  # Get variable & value
  parts = arg.split('=')
  var = parts[0]
  val = parts[1]

  # Check variable to change
  match var:
    # Search mode
    case 'm' | 'mode':
      match val.lower():
        case 'f' | 'fast':
          searchMode = SearchMode.Fast
        case 'c' | 'complete' | _:
          searchMode = SearchMode.Complete

    # Save format
    case 's' | 'save':
      match val.lower():
        case 't' | 'text' | 'txt':
          saveFormat = SaveFormat.Text
        case 'j' | 'json' | _:
          saveFormat = SaveFormat.JSON

# Search mails
mails = findMail(searchMode)

# Save mails to file
match saveFormat:
  # Save as JSON
  case SaveFormat.JSON:
    file = open('mails.json', 'w')
    json.dump(mails, file)
    file.close()
    
  # Save as TXT
  case SaveFormat.Text:
    file = open('mails.txt', 'w')
    for i, mail in enumerate(mails):
      file.write(mail + ':' + str(mails[mail]))
      if (i < len(mails) - 1): file.write('\n')
    file.close()