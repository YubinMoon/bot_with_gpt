import random

import discord
from discord.ext.commands import Context

from bot import ServantBot

from .base import BaseHandler


class ShuffleTeamHandler(BaseHandler):
    LANE = ["탑", "정글", "미드", "원딜", "서폿"]

    def __init__(self, bot: ServantBot, context: Context, team_name: str) -> None:
        super().__init__(bot, context, team_name, "new_team_handler")
        self.base_weight = [[10000.0 for _ in range(5)] for _ in range(5)]
        self.multiple = 0.1

    async def run(self):
        await self.update_team_name()
        self.message_id = await self.db.get_message_id(self.guild.name, self.team_name)
        if self.message_id is None:
            await self.handle_no_team()
            return
        self.members = await self.db.get_members(self.guild.name, self.team_name)
        if len(self.members) not in [5, 10]:
            await self.handle_member_num_check()
        if len(self.members) == 5:
            await self.shuffle_rank()
        elif len(self.members) == 10:
            await self.shuffle_custom()

    async def shuffle_rank(self) -> None:
        team = await self.get_rank_team()
        await self.db.add_history(self.guild.name, self.team_name, team)
        members = [self.guild.get_member(member) for member in self.members]
        members = [member for member in members if member is not None]
        embed = discord.Embed(
            description="라인을 배정했어요.",
            color=0xBEBEFE,
        )
        for l, m in enumerate(team):
            member = members[m]
            embed.add_field(
                name=self.LANE[l],
                value=f"{member.mention} ({member.global_name})",
                inline=False,
            )
        await self.context.send(embed=embed)

    async def shuffle_custom(self) -> None:
        random.shuffle(self.members)
        members = [self.guild.get_member(member) for member in self.members]
        members = [member for member in members if member is not None]
        embed = discord.Embed(
            description="새로운 대전을 구성했어요.",
            color=0xBEBEFE,
        )
        embed.add_field(
            name="1팀",
            value="\n".join(
                [f"{member.mention} ({member.global_name})" for member in members[:5]]
            ),
            inline=False,
        )
        embed.add_field(
            name="2팀",
            value="\n".join(
                [f"{member.mention} ({member.global_name})" for member in members[5:]]
            ),
            inline=False,
        )
        await self.context.send(embed=embed)

    async def get_rank_team(self) -> list[int]:
        team = []
        weights = await self.get_weight()
        while len(set(team)) != 5:
            team.clear()
            for i in range(5):
                team.append(random.choices(range(5), weights=weights[i])[0])
        _team = team.copy()
        for i, member in enumerate(team):
            _team[member] = i
        return _team

    async def get_weight(self) -> list[list[float]]:
        weight = self.base_weight.copy()
        records = await self.db.get_history(self.guild.name, self.team_name)
        for record in records:
            weight = self.calc_weight(weight, record)
        return weight

    def calc_weight(
        self, weight: list[list[float]], record: list[int]
    ) -> list[list[float]]:
        new_weight = weight.copy()
        for lane_no, member_no in enumerate(record):
            remain = (new_weight[member_no][lane_no] * (1 - self.multiple)) // 4
            for i in range(5):
                if i == lane_no:
                    new_weight[member_no][i] -= remain * 4
                else:
                    new_weight[member_no][i] += remain
        return new_weight

    async def handle_member_num_check(self):
        embed = discord.Embed(
            title="팀 인원이 5명 또는 10명이 아니에요.",
            description="팀 인원을 확인해 주세요.",
            color=0xE02B2B,
        )
        await self.context.send(embed=embed, ephemeral=True, silent=True)
        self.logger.warning(
            f"{self.context.author.name} tried to shuffle team with wrong member number."
        )
