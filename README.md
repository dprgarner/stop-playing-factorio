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

## Stuff

```bash
$ pex "." --console-script spfactorio  --output-file app.pex
```

## Links

- https://discordpy.readthedocs.io/en/latest/faq.html
- https://discord.com/developers/docs/quick-start/overview-of-apps
- https://medium.com/@benmorel/creating-a-linux-service-with-systemd-611b5c8b91d6
- https://pex.readthedocs.io/en/v2.1.163/recipes.html
- https://builtin.com/software-engineering-perspectives/discord-bot-python
- https://serverfault.com/questions/413397/how-to-set-environment-variable-in-systemd-service
