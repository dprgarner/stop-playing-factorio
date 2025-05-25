# Stop Playing Factorio Bot

A silly bot to tell people to stop playing Factorio.

![No more Factorio](./icon.png)

## Installing the bot on your server

https://discord.com/oauth2/authorize?client_id=1374351019819012168

## Development

The bot runs in Python using [discord.py](https://discordpy.readthedocs.io/en/latest/intro.html#installing), which uses the [Gateway API](https://discord.com/developers/docs/events/gateway) which communicates with Discord via a persistent Websocket connection. To run the bot locally:

1. Set up and activate a Python 3.8+ virtual environment.
1. Install the dependencies in an editable environment with `pip install -e .`.
1. Create a Discord bot with permissions enabled for the Presences and Guild (Server) Members privileged intents, and "bot" permissions on Guild Install.
1. Add the bot token to a `.env` file as the env variable `DISCORD_TOKEN`.
1. `python -m stop_playing_factorio`
1. Enjoy being sassed by a bot ⚙️❌

## "Deployment" Notes

The bot is currently running on a Raspberry Pi.

There's a systemctl file at `/etc/systemd/system/spfbot.service` (symlinked to the source-controlled one), and it's enabled to run on start-up.

The repo is checked out with a virtual env at `./venv`, and there's a simple `./run.sh` script to activate the env and run the bot module.

The aiohttp wheel takes a while to build on the pi, and needs `apt-get install python3-dev` for the compilation.

```bash
$ sudo systemctl status spfbot
$ tail -f /home/pi/stop-playing-factorio/spfbot.log
```
