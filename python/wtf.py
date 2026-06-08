import os
import webbrowser
redirect = 1
def PRINT(txt):
    print(txt)
def help():
    print("exit -> leave the app")
    print("help -> show a lost of all available commands")
    print("noredirect -> show a link instead of redirecting")
    print("redirect -> redirect instead of showing a link (default)")
def start():
    PRINT("official product by the SCP foundation, distributed through KULEDEVER")
    PRINT("WELCOME TO SCP REASERCHER")
    PRINT("TYPE IN THE NUMBER ONLY AND YOU WILL BE REDIRECTED TO IT")
    PRINT("OPTIONALLY, TYPE 'noredirect' TO SHOW THE LINK TO THE PAGE INSTEAD OF REDIRCTING YOU")
    PRINT("Type help for all commands")
start()
run = True
while run:
    num = input(">")
    if num == "":
        print("Please input a command or number, type help for all commands")
    else:
        if num.isalpha() == True:
            if num == "exit":
                run = False
            elif num == "noredirect":
                redirect = 0
            elif num == "redirect":
                redirect = 1
            elif num == "help":
                help()
            elif num == "clear":
                os.system("cls")
            else:
                print("Please input a valid command, type help for all commands")
        if num.isnumeric() == True:
            if redirect == 0:
                print(f"https://scp-wiki.wikidot.com/scp-{num}")
            elif redirect == 1:
                print("OPENING")
                webbrowser.open(f"https://scp-wiki.wikidot.com/scp-{num}")
        else:
            print("Please input a valid command or number, type help for all commands")
            print("If you are trying to enter the number of an SCP, please insert only the number")