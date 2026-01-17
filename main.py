import os
import math
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Configuration
load_dotenv ()
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
TOKEN = os.environ.get("DISCORD_TOKEN")
# Training times per tier (seconds)
TRAIN_TIME_PER_TIER = {
    't5': 83,  # 1 minute 23 seconds
    't4': 56,  # 56 seconds
}
TRAINING_BUFF = 0.45  # 45% buff

# Base costs per unit by tier
TROOP_COSTS = {
    't5': {
        'mage':   {'wood': 800, 'ore': 600, 'mana': 400, 'gold': 0},
        'infantry': {'wood': 800, 'ore': 0,   'mana': 400, 'gold': 800},
        'cavalry': {'wood': 480, 'ore': 480, 'mana': 400, 'gold': 480},
        'archer':  {'wood': 0,   'ore': 800, 'mana': 400, 'gold': 800},
    },
    't4': {
        'mage':     {'wood': 300, 'ore': 225, 'mana': 100, 'gold': 0},
        'infantry': {'wood': 300, 'ore': 0,   'mana': 100, 'gold': 300},
        'cavalry':  {'wood': 180, 'ore': 180, 'mana': 100, 'gold': 180},
        'archer':   {'wood': 0,   'ore': 225, 'mana': 100, 'gold': 300},
    }
}

def calc_resources(tier: str, unit: str, amount: int):
    tier = tier.lower()
    unit = unit.lower()
    if tier not in TROOP_COSTS:
        return None
    if unit not in TROOP_COSTS[tier]:
        return None
    per = TROOP_COSTS[tier][unit]
    total = {k: v * amount for k, v in per.items()}
    return total

def calc_times(tier: str, amount: int, buff_fraction: float = None):
    tier = tier.lower()
    base = TRAIN_TIME_PER_TIER.get(tier, TRAIN_TIME_PER_TIER.get('t5', 83))
    if buff_fraction is None:
        buff_fraction = TRAINING_BUFF
    per_unit = base * (1 - buff_fraction)
    total_seconds = per_unit * amount
    return per_unit, total_seconds

def format_seconds(seconds: float):
    seconds = int(round(seconds))
    days, rem = divmod(seconds, 86400)
    hrs, rem = divmod(seconds, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hrs:
        parts.append(f"{hrs}h")
    if mins:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")
    return ' '.join(parts)


def human_format(n: int) -> str:
    """Return a human-friendly string for large integers (e.g. 300K, 1.2M)."""
    try:
        n = int(n)
    except Exception:
        return str(n)
    abs_n = abs(n)
    if abs_n >= 1_000_000_000:
        val = n / 1_000_000_000
        s = f"{val:.2f}B"
    elif abs_n >= 1_000_000:
        val = n / 1_000_000
        s = f"{val:.2f}M"
    elif abs_n >= 1_000:
        val = n / 1_000
        s = f"{val:.2f}K"
    else:
        return f"{n:,}"
    # strip unnecessary trailing zeros and dot
    s = s.replace('.00', '')
    s = s.replace('.0', '')
    return s

class TrainBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix='!', intents=intents)

    async def setup_hook(self) -> None:
        self.tree.add_command(train)
        await self.tree.sync()



@app_commands.command(name='train', description='Calculate resources and training time for troops')
@app_commands.describe(tier='Tier (e.g. t5)', unit='Unit type (mage, infantry, cavalry, archer)', amount='Amount to train', buff='Training buff percentage (e.g. 45 for 45%)')
async def train(interaction: discord.Interaction, tier: str, unit: str, amount: int, buff: float = None):
    """Slash command: /train tier unit amount"""
    await interaction.response.defer()
    tier_l = tier.lower()
    unit_l = unit.lower()
    if amount <= 0:
        await interaction.followup.send('Amount must be a positive integer.')
        return

    # parse optional buff percentage from user (expected as percent like 45)
    if buff is not None:
        try:
            buff_pct = float(buff)
        except (TypeError, ValueError):
            await interaction.followup.send('Buff must be a number (percentage), e.g. 45 for 45%')
            return
        if buff_pct < 0 or buff_pct > 100:
            await interaction.followup.send('Buff percentage must be between 0 and 100.')
            return
        buff_fraction = buff_pct / 100.0
    else:
        buff_fraction = TRAINING_BUFF

    resources = calc_resources(tier_l, unit_l, amount)
    if resources is None:
        if tier_l not in TROOP_COSTS:
            await interaction.followup.send(f'Costs for tier `{tier}` are not defined yet. Provide base numbers to add support.')
        else:
            await interaction.followup.send(f'Unknown unit `{unit}` for {tier}. Valid: {", ".join(TROOP_COSTS[tier_l].keys())}')
        return

    per_unit, total_seconds = calc_times(tier_l, amount, buff_fraction)

    lines = []
    lines.append(f'**Training:** {human_format(amount)} × {tier.upper()} {unit.capitalize()}')
    res_parts = []
    for k in ['wood', 'ore', 'mana', 'gold']:
        v = resources.get(k, 0)
        if v:
            res_parts.append(f'{human_format(v)} {k}')
    if res_parts:
        lines.append('**Resources:** ' + ', '.join(res_parts))
    else:
        lines.append('**Resources:** None')

    lines.append(f'**Time per unit (with {buff_fraction*100:.2f}% buff):** {per_unit:.2f}s ({format_seconds(per_unit)})')
    lines.append(f'**Total training time:** {format_seconds(total_seconds)}')

    await interaction.followup.send('\n'.join(lines))
    bot = TrainBot()


if __name__ == '__main__':
    if not TOKEN:
        print('Error: set DISCORD_TOKEN environment variable before running.')
    else:
        bot.run(TOKEN)



