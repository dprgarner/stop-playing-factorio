# Stop Playing Factorio Bot

A silly bot to tell people to stop playing Factorio.

![No more Factorio](./icon.png)

## Installation instructions

1. Set up and activate a Python 3.8+ virtual environment.
1. Install the dependencies in an editable environment with `pip install -e .`. (See [Discord docs](https://discordpy.readthedocs.io/en/latest/intro.html#installing) if this doesn't work).
1. Create a Discord bot with the Presences, Server Members, and Message Content permissions.
1. Add the bot token to a `.env` file as the env variable `TOKEN`.
1. `python -m stop_playing_factorio`
1. Enjoy being sassed by a bot ⚙️❌

## Notes

This is currently running on the Raspberry Pi.

There's a systemctl file at `/etc/systemd/system/spfbot.service`, and it's enabled on start-up.

Pex didn't work because aiohttp needs some ARM-built stuff, so I copied the repo across and installed it with a new venv.

The aiohttp wheel takes a while to build on the pi, and also needed `apt-get install python3-dev` for the compilation.

```bash
$ systemctl status spfbot
$ tail -f /home/pi/stop-playing-factorio/spfbot.log
```
