# Glossary

Words used in code, docs and tickets. Real names never appear in this repo; they live only in private config.

## Household

- **Cat**: the pet that uses the Litter Box.
- **Dog**: the pet that may try to eat Poop from the Litter Box.
- **Partner**: the person who is told about events by a Speaker.

## Litter Box

- **Litter Box**: the open box the camera watches. The camera can see the litter surface.
- **Visit**: one stay by the Cat in the Litter Box, from going in to coming out.
- **Outcome**: what a Visit left behind: **Pee**, **Poop**, or **Nothing**.
- **Outcome Guess**: an early guess at the Outcome made while the Visit is still going, from things like the Cat's stance and the time of day. The real Outcome is decided from the litter surface after the Visit.
- **Poop Reminder**: an Announcement that Poop is still in the Litter Box. Reminders get further apart each time and stop after a set time or count.
- **Dog at Poop**: the Dog is at the Litter Box while Poop is still in it. A Dog near an empty box is not this.

## Telling people

- **Listener**: a person on the list who may hear Announcements, such as the Partner.
- **Presence**: whether a Listener is **Home**, **Away**, or **Unknown** (the check is off or not working).

- **Speaker**: a Google Home or Alexa device that can say a message out loud.
- **Announcement**: a message a Speaker says to the Partner about an event.
- **Quiet Hours**: a repeating time, such as weeknights 10pm to 7am, when Announcements are held back. There can be many.
- **Do Not Disturb**: a one-off quiet time switched on now until a set end time.
- **Urgency**: how important an Announcement is: **Info**, **Normal** or **Urgent**. Quiet Hours and Do Not Disturb say which Urgencies may still be spoken. Urgency is never spoken aloud.

## Problems

- **Camera Offline**: no picture from the camera for a set time. **Login Expired** is the kind of Camera Offline that needs a person to log in again.

## Data

- **Private Data Store**: the place on the home network (the NAS) where clips, pictures, labels and other private files live. It is never part of the repo.
