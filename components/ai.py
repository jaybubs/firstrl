from __future__ import annotations

import random
from typing import Optional, List, Tuple, TYPE_CHECKING

import numpy as np
import tcod

from actions import Action, BumpAction, MeleeAction, MovementAction, WaitAction

if TYPE_CHECKING:
    from entity import Actor


class BaseAI(Action):
    def perform(self) -> None:
        raise NotImplementedError()

    def get_path_to(
        self,
        dest_x: int,
        dest_y: int,
    ) -> List[Tuple[int, int]]:
        # compute and return a path to target
        # if no valid path then return empty list
        # copy the walkable array
        cost = np.array(self.entity.gamemap.tiles["walkable"], dtype=np.int8)

        for entity in self.entity.gamemap.entities:
            # check an entity blocks movement and cost not zero
            if entity.blocks_movement and cost[entity.x, entity.y]:
                # add to the cost of a blocked position
                # lower number more enemies will crowd behind each other
                # higher number means enemies will take longer paths to surround the playre
                cost[entity.x, entity.y] += 10

        # create a graph from the cost array and pass to a new pathfinder
        graph = tcod.path.SimpleGraph(cost=cost, cardinal=2, diagonal=3)
        pathfinder = tcod.path.Pathfinder(graph)

        pathfinder.add_root((self.entity.x, self.entity.y))  # start position
        # compute the path to the destination and remove the starting point
        path: List[List[int]] = pathfinder.path_to((dest_x, dest_y))[1:].tolist()

        # convert from ListList to ListTuple
        return [(index[0], index[1]) for index in path]


class ConfusedEnemy(BaseAI):
    """
    a confused enemy will stumble around for a few rounds. it will still attack if near player
    """

    def __init__(
        self,
        entity: Actor,
        previous_ai: Optional[BaseAI],
        turns_remaining: int,
    ):
        super().__init__(entity)

        self.previous_ai = previous_ai
        self.turns_remaining = turns_remaining

    def perform(self) -> None:
        # revert the ai back to the original state
        if self.turns_remaining <= 0:
            self.engine.message_log.add_message(
                f"The {self.entity.name} is no longer confused"
            )
            self.entity.ai = self.previous_ai
        else:
            # pick a random direction
            direction_x, direction_y = random.choice(
                [
                    (-1, -1),  # Northwest
                    (0, -1),  # North
                    (1, -1),  # Northeast
                    (-1, 0),  # West
                    (1, 0),  # East
                    (-1, 1),  # Southwest
                    (0, 1),  # South
                    (1, 1),  # Southeast
                ]
            )

            self.turns_remaining -= 1

            # the actor will either try to move or attack in the chosen random direction
            # its possible the actor will just bump into the wall wasting a turn
            return BumpAction(self.entity, direction_x, direction_y).perform()


class HostileEnemy(BaseAI):
    def __init__(self, entity: Actor):
        super().__init__(entity)
        self.path: List[Tuple[int, int]] = []

    def perform(self) -> None:
        target = self.engine.player
        dx = target.x - self.entity.x
        dy = target.y - self.entity.y
        distance = max(abs(dx), abs(dy))  # chebyshev distance

        if self.engine.game_map.visible[self.entity.x, self.entity.y]:
            if distance <= 1:
                return MeleeAction(self.entity, dx, dy).perform()

            self.path = self.get_path_to(target.x, target.y)

        if self.path:
            dest_x, dest_y = self.path.pop(0)
            return MovementAction(
                self.entity,
                dest_x - self.entity.x,
                dest_y - self.entity.y,
            ).perform()

        return WaitAction(self.entity).perform()
