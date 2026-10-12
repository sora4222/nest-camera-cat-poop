# Alexa Smart Home skill

Speaker kind `alexa` makes an Echo say each message for free, with Amazon's official APIs and no third party. It works through routines:

1. Our Smart Home skill shows one virtual motion sensor per message kind in `[messages]`, named "Litter box poop", "Litter box visit started" and so on.
2. In the Alexa app you make one routine per sensor: *when "Litter box poop" detects motion, Alexa says "Lacey left poop in the litter box"*.
3. When the watcher says a message, the `alexa` speaker finds its kind and tells Alexa that sensor saw motion. The routine runs.

The words are the ones you type into each routine, so keep them in step with `[messages]`. Messages with details (such as `{guess}`) still fire their sensor, but the routine says its fixed text.

```
Watcher --ChangeReport--> Alexa Event Gateway --> routine --> Echo speaks
Alexa --directive--> our Lambda --HTTPS + secret--> tunnel --> 127.0.0.1:8767/alexa/smart-home
```

Amazon only sends Smart Home directives (discovery, linking, state) to AWS Lambda, so a tiny Lambda, [`alexa/smart_home_lambda.py`](../alexa/smart_home_lambda.py), forwards them to the watcher through the same tunnel as the [custom skill](alexa-skill.md). It fits easily in Lambda's free tier.

## Security

- `/alexa/smart-home` only answers requests carrying `Authorization: Bearer <CATPOOP_ALEXA_SMART_HOME_SECRET>`; anything else gets 401. Use a long random secret (`openssl rand -hex 32`).
- Linking stores a Login with Amazon refresh token in `~/.local/state/catpoop/alexa-grant.json`, readable only by you. Tokens and secrets are never logged.
- All secrets go in `.env`, best as 1Password references.

## Set up

Use the Amazon account the Echo uses. "Region" is NA (US, Canada), EU (UK, Europe) or FE (Australia, Japan, India).

1. **Make the skill.** In the [Alexa developer console](https://developer.amazon.com/alexa/console/ask), **Create Skill**, model **Smart Home**. Copy its skill ID.
2. **Make the Lambda.** In the AWS console, in us-east-1 (NA), eu-west-1 (EU) or us-west-2 (FE), create a Python 3.12 function and paste `alexa/smart_home_lambda.py`. Set its environment variables `CATPOOP_URL=https://<your tunnel host>/alexa/smart-home` and `CATPOOP_SECRET=<the secret>`. Add the trigger **Alexa Smart Home** with the skill ID. Copy the function's ARN into the skill's **Default endpoint**.
3. **Account linking.** In [Login with Amazon](https://developer.amazon.com/loginwithamazon/console/site/lwa/overview.html), make a security profile. In the skill's **Account Linking**: authorization URI `https://www.amazon.com/ap/oa`, token URI `https://api.amazon.com/auth/o2/token`, the profile's client ID and secret, scope `profile:user_id`. Add the skill's **Alexa Redirect URLs** to the profile's allowed return URLs.
4. **Send events.** In the skill's **Permissions**, turn on **Send Alexa Events** and copy the Alexa client ID and secret.
5. **Configure the watcher.** In `.env`:

   ```sh
   CATPOOP_ALEXA_SMART_HOME_SECRET=op://Private/cat-poop-alexa-smart-home/secret
   CATPOOP_ALEXA_CLIENT_ID=op://Private/cat-poop-alexa-smart-home/client_id
   CATPOOP_ALEXA_CLIENT_SECRET=op://Private/cat-poop-alexa-smart-home/client_secret
   ```

   In `config.toml`, turn on `[alexa_skill]` with `smart_home = true` (see [alexa-skill.md](alexa-skill.md) for the tunnel; run `make alexa-tunnel` again so it also forwards `/alexa/smart-home`), and add the speaker:

   ```toml
   [[speakers]]
   name = "Echo"
   kind = "alexa"
   region = "FE"
   ```

   Restart the watcher.
6. **Link it.** In the Alexa app, **Skills > Your Skills > Dev**, enable the skill and sign in. Alexa then finds the sensors. If not, say "Alexa, discover devices".
7. **Make the routines.** For each sensor: **Routines > +**, *When this happens* **Smart Home >** the sensor **> Detects motion**, *Add action* **Alexa Says > Customised**, type the message, and pick the Echo under *From*.

If you add a message kind later, run discovery again and add its routine.
