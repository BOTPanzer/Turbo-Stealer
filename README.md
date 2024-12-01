# Disclaimer

For **educational purposes** only, this repository shows people how insecure some information is in our computers and wants to spread awareness.  

# TurboStealer

Command line app that steals information from the user. Currently, only emails can be stolen.

# Usage

Just open **TurboStealer.exe** and a file containing the stolen information will be created.

# Settings

Some settings can be changed by using command line arguments:

- ```m``` or ```mode```:  
Changes the mode that is used to search for emails.  
**Example:** ```TurboStealer.exe mode=fast```  
  - ```f``` or ```fast```:  
  Sets the mode to fast. In this mode, if a method finds an email it will stop.
  - ```c``` or ```complete``` ***default***:  
  Sets the mode to complete. In this mode all methods will be used.

- ```s``` or ```save```:  
Changes the save format that is used to save the emails.  
**Example:** ```TurboStealer.exe save=text```  
  - ```t```, ```text``` or ```txt```:  
  Saves the info in plain text.
  - ```j``` or ```json``` ***default***:  
  Saves the info in a JSON file.