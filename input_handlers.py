from __future__ import annotations
import os
from typing import Optional, TYPE_CHECKING, Tuple, Callable, Union
import tcod
import actions
from actions import Action, BumpAction, WaitAction, PickupAction
import color
import exceptions


if TYPE_CHECKING:
    from engine import Engine
    from entity import Item

MOVE_KEYS = {
        #arrows
        tcod.event.K_UP: (0, -1),
        tcod.event.K_DOWN: (0, 1),
        tcod.event.K_LEFT: (-1, 0),
        tcod.event.K_RIGHT: (1, 0),
        tcod.event.K_HOME: (-1, -1),
        tcod.event.K_END: (-1, 1),
        tcod.event.K_PAGEUP: (1, -1),
        tcod.event.K_PAGEDOWN: (1, 1),
        }
WAIT_KEYS = {
        tcod.event.K_PERIOD
        }

CONFIRM_KEYS = {
        tcod.event.K_RETURN,
        tcod.event.K_KP_ENTER,
        }

ActionOrHandler = Union[Action, "BaseEventHandler"]
"""an event handler return value which can trigger an action or switch active handlers
if a handler is returned then it will become the active handler for future events
if an action si returned it will be attempted and if it's valid the maingameventhandler will become the active handler
"""

class BaseEventHandler(tcod.event.EventDispatch[ActionOrHandler]):
    def handle_events(self, 
            event: tcod.event.Event) -> BaseEventHandler:
        """handle an event and return the next active event handler"""
        state = self.dispatch(event)
        if isinstance(state, BaseEventHandler):
            return state
        assert not isinstance(state, Action), f"{self!r} can not handle actions"
        return self

    def on_render(self, 
            console: tcod.Console) -> None:
        raise NotImplementedError()

    def ev_quit(self, 
            event: tcod.event.Quit) -> Optional[ActionOrHandler]:
        raise SystemExit()

class PopupMessage(BaseEventHandler):
    """display a popup text window"""
    def __init__(self, 
            parent_handler: BaseEventHandler,
            text: str):
        self.parent = parent_handler
        self.text = text

    def on_render(self, 
            console: tcod.Console) -> None:
        """render the parent and dim the result, then print the message on top"""
        self.parent.on_render(console)
        console.tiles_rgb["fg"] //= 8
        console.tiles_rgb["bg"] //= 8

        console.print(
                console.width // 2,
                console.height // 2,
                self.text,
                fg=color.white,
                bg=color.black,
                alignment=tcod.CENTER,
                )

    def ev_keydown(self, 
            event: tcod.event.KeyDown) -> Optional[BaseEventHandler]:
        """any key returns to the parent handler"""
        return self.parent

class EventHandler(BaseEventHandler):
    def __init__(self, engine: Engine):
        self.engine = engine

    def handle_events(self,
            event: tcod.event.Event,
            ) -> BaseEventHandler:
        """handle events for input handhlers with an engine"""
        action_or_state = self.dispatch(event)
        if isinstance(action_or_state, BaseEventHandler):
            return action_or_state
        if self.handle_action(action_or_state):
            #a valid action was performed
            if not self.engine.player.is_alive:
                #the player was killed during or after the action
                return GameOverEventHandler(self.engine)
            return MainGameEventHandler(self.engine) #return to the main handler
        return self

    def handle_action(self, 
            action: Optional[ActionOrHandler]) -> bool:
        """handle actions returned from event methods
        returns true if the action will advance a turn"""
        if action is None:
            return False

        try:
            action.perform()
        except exceptions.Impossible as exc:
            self.engine.message_log.add_message(exc.args[0], color.impossible)
            return False #skip enemy turn on exceptions

        self.engine.handle_enemy_turns()

        self.engine.update_fov()
        return True

    def ev_mousemotion(self,
            event: tcod.event.MouseMotion,
            ) -> None:
        if self.engine.game_map.in_bounds(event.tile.x, event.tile.y):
            self.engine.mouse_location = event.tile.x, event.tile.y

    def on_render(self,
            console: tcod.Console,
            ) -> None:
        self.engine.render(console)

class MainGameEventHandler(EventHandler):

    def ev_keydown(self, event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        action: Optional[ActionOrHandler] = None

        key = event.sym

        player = self.engine.player

        if key in MOVE_KEYS:
            dx, dy = MOVE_KEYS[key]
            action = BumpAction(player, dx, dy)
        elif key in WAIT_KEYS:
            action = WaitAction(player)


        elif key == tcod.event.K_ESCAPE:
            raise SystemExit()
        elif key == tcod.event.K_v:
            return HistoryViewer(self.engine)
        elif key == tcod.event.K_g:
            action = PickupAction(player)

        elif key == tcod.event.K_i:
            return InventoryActivateHandler(self.engine)
        elif key == tcod.event.K_d:
            return InventoryDropHandler(self.engine)
        elif key == tcod.event.K_SLASH:
            return LookHandler(self.engine)

        # no valid key pressed
        return action

class GameOverEventHandler(EventHandler):

    def on_quit(self) -> None:
        """handle exiting out of a finished game"""
        if os.path.exists("savegame.sav"):
            os.remove("savegame.sav") #deletes the active save file
        raise exceptions.QuitWithoutSaving() #avoid saving a finished game

    def ev_quit(self, 
            event: tcod.event.Quit) -> None:
        self.on_quit()

    def ev_keydown(self, event: tcod.event.KeyDown) -> None:

        if event.sym == tcod.event.K_ESCAPE:
            self.on_quit()

CURSOR_Y_KEYS = {
        tcod.event.K_UP: -1,
        tcod.event.K_DOWN: 1,
        tcod.event.K_PAGEUP: -10,
        tcod.event.K_PAGEDOWN: 10,
        }

class HistoryViewer(EventHandler):
    """print the history on a larger window which can be navigated"""

    def __init__(self, engine: Engine):
        super().__init__(engine)
        self.log_length = len(engine.message_log.messages)
        self.cursor = self.log_length - 1

    def on_render(self, 
            console: tcodConsole) -> None:
        super().on_render(console) # draw the main state as the background

        log_console = tcod.Console(console.width - 6, console.height - 6)

        #draw a frame with a custom banner title
        log_console.draw_frame(0, 0, log_console.width, log_console.height)
        log_console.print_box(0, 0, log_console.width, 1, "|Message History|", alignment=tcod.CENTER)

        #render the message log using the cursor parameter
        self.engine.message_log.render_messages(
                log_console,
                1,
                1,
                log_console.width - 2,
                log_console.height - 2,
                self.engine.message_log.messages[: self.cursor +1],
                )
        log_console.blit(console, 3, 3)

    def ev_keydown(self, 
            event: tcod.event.KeyDown) -> Optional[MainGameEventHandler]:
        #fancy conditional movement to make it feel right
        if event.sym in CURSOR_Y_KEYS:
            adjust = CURSOR_Y_KEYS[event.sym]
            if adjust < 0 and self.cursor == 0:
                # Only move from the top to the bottom when you're on the edge.
                self.cursor = self.log_length - 1
            elif adjust > 0 and self.cursor == self.log_length - 1:
                # Same with bottom to top movement.
                self.cursor = 0
            else:
                # Otherwise move while staying clamped to the bounds of the history log.
                self.cursor = max(0, min(self.cursor + adjust, self.log_length - 1))
        elif event.sym == tcod.event.K_HOME:
            self.cursor = 0  # Move directly to the top message.
        elif event.sym == tcod.event.K_END:
            self.cursor = self.log_length - 1  # Move directly to the last message.
        else:  # Any other key moves back to the main game state.
            return MainGameEventHandler(self.engine)
        return None

class AskUserEventHandler(EventHandler):
    """handles user input for actions which require special input"""

    def ev_keydown(self, 
            event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """by default any key exits this input handler"""
        if event.sym in { #ignore modifiers
                tcod.event.K_LSHIFT,
                tcod.event.K_RSHIFT,
                tcod.event.K_LCTRL,
                tcod.event.K_RCTRL,
                tcod.event.K_LALT,
                tcod.event.K_RALT,
                }:
            return None
        return self.on_exit()

    def ev_mousebuttondown(self,
            event: tcod.event.MouseButtonDown) -> Optional[ActionOrHandler]:
        """by default any mouse click exits this input handler"""
        return self.on_exit()

    def on_exit(self) -> Optional[ActionOrHandler]:
        """called when the user is trying to exit or cancel an action
        by default this returns to the main event handler
        """
        return MainGameEventHandler(self.engine)

class InventoryEventHandler(AskUserEventHandler):
    """this handler lets the user select an item
    what happens depends on the subclass"""
    TITLE = "<missing title>"

    def on_render(self, 
            console: tcod.Console) -> None:
        """render an inventory menu which displays the inventory items
        select with corresponding letter
        move to a different position based on user location so the playre can see where they are"""
        
        super().on_render(console)
        number_of_items_in_inventory = len(self.engine.player.inventory.items)

        height = number_of_items_in_inventory + 2

        if height <= 3:
            height = 3

        if self.engine.player.x <= 30:
            x = 40
        else:
            x = 0

        y = 0
        width = len(self.TITLE) + 4

        console.draw_frame(
                x=x,
                y=y,
                width=width,
                height=height,
                title=self.TITLE,
                clear=True,
                fg=(255, 255, 255),
                bg=(0,0,0),
                )

        if number_of_items_in_inventory > 0:
            for i, item in enumerate(self.engine.player.inventory.items):
                item_key = chr(ord("a") +i )
                console.print(x+1, y+i+1, f"({item_key}) {item.name}")
        else:
            console.print(x+1, y+1, "(Empty)")

    def ev_keydown(self, 
            event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        player = self.engine.player
        key = event.sym
        index = key - tcod.event.K_a

        if 0 <= index <= 26:
            try:
                selected_item = player.inventory.items[index]
            except IndexError:
                self.engine.message_log.add_message("invalid entry", color.invalid)
                return None
            return self.on_item_selected(selected_item)
        return super().ev_keydown(event)

    def on_item_selected(self, 
            item: Item) -> Optional[ActionOrHandler]:
        """called when the user selects a valid item"""
        raise NotImplementedError()

class InventoryActivateHandler(InventoryEventHandler):
    """handle using an inventory item"""
    TITLE = "select an item to use"

    def on_item_selected(self,
            item: Item) -> Optional[ActionOrHandler]:
        """return the action for the selected item"""
        return item.consumable.get_action(self.engine.player)

class InventoryDropHandler(InventoryEventHandler):
    """handle dropping an inventory item"""

    TITLE = "select an item to drop"

    def on_item_selected(self, 
            item: Item) -> Optional[ActionOrHandler]:
        """drop this item"""
        return actions.DropItem(self.engine.player, item)

class SelectIndexHandler(AskUserEventHandler):
    """handles asking the user for an index on the map"""

    def __init__(self, 
            engine: Engine):
        """sets the cursor to the player when this handler is constructed"""
        super().__init__(engine)
        player = self.engine.player
        engine.mouse_location = player.x, player.y

    def on_render(self, 
            console: tcod.Console) -> None:
        """highlight the tile under the cursor"""
        super().on_render(console)
        x, y = self.engine.mouse_location
        console.tiles_rgb["bg"][x,y] = color.white
        console.tiles_rgb["fg"][x,y] = color.black

    def ev_keydown(self, 
            event: tcod.event.KeyDown) -> Optional[ActionOrHandler]:
        """check for key movement or confirmation keys"""
        key = event.sym
        if key in MOVE_KEYS:
            modifier = 1 #holding modifier keys will speed up key movement
            if event.mod & (tcod.event.KMOD_LSHIFT | tcod.event.KMOD_RSHIFT):
                modifier *= 5
            if event.mod & (tcod.event.KMOD_LCTRL | tcod.event.KMOD_RCTRL):
                modifier *= 10
            if event.mod & (tcod.event.KMOD_LALT | tcod.event.KMOD_RALT):
                modifier *= 20

            x, y = self.engine.mouse_location
            dx, dy = MOVE_KEYS[key]
            x += dx * modifier
            y += dy * modifier
            #clamp the cursor index to the map size
            x = max(0, min(x, self.engine.game_map.width -1))
            y = max(0, min(y, self.engine.game_map.height -1))
            self.engine.mouse_location = x, y
            return None
        elif key in CONFIRM_KEYS:
            return self.on_index_selected(*self.engine.mouse_location)
        return super().ev_keydown(event)

    def ev_mousebuttondown(self, 
            event: tcod.event.MouseButtonDown) -> Optional[ActionOrHandler]:
        """left click confirms a selection"""
        if self.engine.game_map.in_bounds(*event.tile):
            if event.button == 1:
                return self.on_index_selected(*event.tile)
            return super().ev_mousebuttondown(event)

    def on_index_selected(self, 
            x: int,
            y: int) -> Optional[ActionOrHandler]:
        """called when an index is selected"""
        raise NotImplementedError()

class LookHandler(SelectIndexHandler):
    """lets the player look around using the keyboard"""

    def on_index_selected(self, 
            x: int,
            y: int) -> MainGameEventHandler:
        """return to main handler"""
        return MainGameEventHandler(self.engine)

class SingleRangedAttackHandler(SelectIndexHandler):
    """handles targeting and affecting a single enemy"""

    def __init__(self, 
            engine: Engine,
            callback: Callable[[Tuple[int,int]], Optional[ActionOrHandler]],
            ):
        super().__init__(engine)
        self.callback = callback

    def on_index_selected(self, 
            x: int,
            y: int) -> Optional[ActionOrHandler]:
        return self.callback((x,y))

class AreaRangedAttackHandler(SelectIndexHandler):
    """handles targeting an area within a given radius"""

    def __init__(self, 
            engine: Engine,
            radius: int,
            callback: Callable[[Tuple[int,int]], Optional[ActionOrHandler]],
            ):
        super().__init__(engine)

        self.radius = radius
        self.callback = callback

    def on_render(self, 
            console: tcod.Console) -> None:
        """highlight the tile under the cursor"""
        super().on_render(console)

        x,y = self.engine.mouse_location

        #draw a rectangle around teh targeted area
        console.draw_frame(
                x = x - self.radius - 1,
                y = y - self.radius - 1,
                width = self.radius **2,
                height = self.radius **2,
                fg = color.red,
                clear = False,
                )
    def on_index_selected(self, 
            x: int,
            y: int) -> Optional[ActionOrHandler]:
        return self.callback((x,y))