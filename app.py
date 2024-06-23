from flask import Flask, jsonify
import os, json, requests, time
from werkzeug.serving import is_running_from_reloader
from multiprocessing import Process

app = Flask(__name__)

credits: dict[
    str, list[
        dict[
            str, str | int
        ]
    ]
] = {}
last_refreshed: int = 0

PORT = os.getenv("PORT", 8000)
DEBUG = os.getenv("DEBUG", False)

GJ_USER_INFO_URL = "http://www.boomlings.com/database/getGJUserInfo20.php"

# originally written by Prevter in JS, translated to Python by ~~me~~ chatgpt
def parse_key_map(key_map):
    keys_values = key_map.split(":")
    return {keys_values[i]: keys_values[i + 1] for i in range(0, len(keys_values), 2)}

def retrieve_credits():
    if not is_running_from_reloader() and DEBUG:
        # flask's default debug functionality runs the script twice
        # while I could disable it, I don't wanna lose live reloading (in debug)
        # so this works as a workaround
        # source: https://stackoverflow.com/a/25504196/20616402
        print("not running from reloader! returning...")
        return

    old_credits: dict[
        str, list[
            dict[
                str, str | int
            ]
        ]
    ] = {}

    # doing this to copy the types over
    new_credits = old_credits.copy()

    temp_cache: dict[int, dict[
        str, str | int
    ]] = {}

    with open("credits.json", "r") as f:
        old_credits = json.load(f)

    for role in old_credits.keys():
        list_len = len(old_credits[role])
        new_credits[role] = [{}] * list_len

        for index in range(list_len):
            new_credit = old_credits[role][index]

            if new_credit["accountID"] in temp_cache:
                print(f"user {new_credit['name']} already in cache, using cached value instead")
                new_credits[role][index] = temp_cache[new_credit["accountID"]]
                continue

            req_start_time = time.time()
            response_text = requests.post(GJ_USER_INFO_URL, data={
                "secret": "Wmfd2893gb7",
                "targetAccountID": new_credit["accountID"]
            }, headers={
                "User-Agent": ""
            }).text
            req_duration = time.time() - req_start_time

            if response_text.split(":")[1] == " 1015": # rate limiting!! (unlikely because we sleep in between requests but whatever)
                print("somehow we're getting rate limited! ending cache update")
                return
            
            if response_text.split(":")[1] == " 1006": # ip blocked!! please setup a proxy
                print("error code 1006 recieved from boomlings. i'm sure you know what to do now")
                return
            
            response = parse_key_map(response_text)

            color1 = int(response["10"])
            color2 = int(response["11"])
            color3 = int(response["51"])
            if int(response["28"]) == 0: color3 = -1
            iconID = int(response["21"])
            gameName = response["1"]

            new_credit["color1"] = color1
            new_credit["color2"] = color2
            new_credit["color3"] = color3
            new_credit["iconID"] = iconID
            new_credit["gameName"] = gameName

            print(new_credit)

            temp_cache[new_credit["accountID"]] = new_credit
            new_credits[role][index] = new_credit

            time.sleep(2 - req_duration)
    
    global credits
    credits = new_credits

@app.get("/")
def index():
    return jsonify("Credit server running!")

@app.get("/credits")
def send_credits():
    return jsonify(credits)

last_modified = 0

def check_credits():
    global last_modified
    global last_refreshed
    while True:
        modified_time = os.path.getmtime("credits.json")
        last_modified = last_modified if last_modified != 0 else modified_time
        if modified_time > last_modified:
            last_modified = modified_time
            print("file changed! retriving credits...")
            retrieve_credits()
            last_refreshed = time.time()

        if time.time() - last_refreshed >= 3600 * 24: # 3600 * 24 = one day (24hrs) in seconds
            print("reloading cache...")
            retrieve_credits()
            last_refreshed = time.time()

process = None
if is_running_from_reloader() or not DEBUG:
    process = Process(target=check_credits)
    process.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG)

if process is not None and DEBUG:
    process.join()