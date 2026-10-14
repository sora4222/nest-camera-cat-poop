"""AWS Lambda for the Smart Home skill: forward each directive to the watcher.

Amazon only sends Smart Home directives to Lambda. Set CATPOOP_URL (for example
https://litter.example.com/alexa/smart-home) and CATPOOP_SECRET (the same as
CATPOOP_ALEXA_SMART_HOME_SECRET) on the function. Python 3.12, standard library only.
"""

import json
import os
import urllib.request


def lambda_handler(event, context):
    """The watcher's answer to `event`."""
    request = urllib.request.Request(
        os.environ["CATPOOP_URL"],
        data=json.dumps(event).encode(),
        headers={
            "Authorization": f"Bearer {os.environ['CATPOOP_SECRET']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=7) as response:
        return json.loads(response.read())
