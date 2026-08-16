from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import re

import flet as ft
import ui.home as ui

from ui.theme.colors import BORDER, PASTEL_BLUE, PASTEL_DARK_PURPLE, PASTEL_PURPLE, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY


EXECUTABLE_SUFFIX_ICON = ft.Icons.ARROW_FORWARD_ROUNDED

ModuleOption = str | Mapping[str, object]


@dataclass(frozen=True)
class ResolvedModule:
    module_id: int | None
    path: str
    argument: str
    ambiguous: bool = False


class HomeDropdowns:
    def __init__(
        self,
        module_options: Sequence[ModuleOption],
        executable_lookup: Mapping[str, bool],
        controls,
        search_arguments: Callable[[int, str], Sequence[ui.argument_dropdown.ArgumentOption]],
        on_select_module: Callable[[int, str], None],
        on_select_argument: Callable[[str], None],
        update_control: Callable[[ft.Control], None],
        dropdown_height: int,
    ):
        # Guarda dependencias e estado visual dos dropdowns da home.
        self.module_options = module_options
        self.executable_lookup = executable_lookup
        self.controls = controls
        self.search_arguments = search_arguments
        self.on_select_module = on_select_module
        self.on_select_argument = on_select_argument
        self.update_control = update_control
        self.dropdown_height = dropdown_height
        self.selected_module_id: int | None = None
        self.selected_module_path: str | None = None
        self.expanded_groups: dict[str, bool] = {}
        self.last_query: str | None = None

    def sync_stack(self) -> None:
        # Ajusta a altura da area dos dropdowns conforme a visibilidade.
        self.controls.dropdown_stack.height = (
            self.dropdown_height
            if self.controls.module_panel.visible or self.controls.argument_panel.visible
            else 0
        )
        self.update_control(self.controls.dropdown_stack)

    def hide_module_suggestions(self) -> None:
        # Fecha e limpa o dropdown principal de modulos.
        self.controls.module_suggestions_list.controls.clear()
        self.controls.module_panel.visible = False

    def hide_argument_suggestions(self) -> None:
        # Fecha e limpa o dropdown secundario de argumentos.
        self.controls.argument_suggestions_list.controls.clear()
        self.controls.argument_panel.visible = False

    def hide_all(self, e=None) -> None:
        # Fecha todos os dropdowns da home.
        self.hide_module_suggestions()
        self.hide_argument_suggestions()
        self.update_control(self.controls.module_panel)
        self.update_control(self.controls.argument_panel)
        self.sync_stack()

    def keep_open(self, e=None) -> None:
        # Mantem o clique interno do dropdown sem acao extra.
        return

    def clear_selected_module(self) -> None:
        # Limpa o modulo atualmente aguardando argumento.
        self.selected_module_id = None
        self.selected_module_path = None

    def toggle_group(self, module_path: str) -> None:
        # Alterna a expansao de uma pasta de modulo.
        self.expanded_groups[module_path] = not self.expanded_groups.get(module_path, False)
        self.show_module_suggestions(self.controls.command_input_field.value or "")

    def show_module_suggestions_from_event(self, e) -> None:
        # Exibe sugestoes de modulo usando o valor do evento do input.
        value = e.control.value or ""
        self.show_module_suggestions(value, reset_empty_groups=not value.strip())

    def show_module_suggestions_from_shell(self, e=None) -> None:
        # Exibe sugestoes quando o usuario clica no shell do input.
        self.show_module_suggestions(self.controls.command_input_field.value or "")

    def refresh_module_suggestions(self, e) -> None:
        # Atualiza sugestoes quando o texto do input principal muda.
        self.clear_selected_module()
        self.hide_argument_suggestions()
        self.show_module_suggestions(e.control.value or "", reset_empty_groups=not (e.control.value or "").strip())

    def show_module_suggestions(self, query: str | None = None, reset_empty_groups: bool = False) -> None:
        # Filtra e renderiza a arvore de modulos no dropdown principal.
        query = query or ""
        matches = filter_modules(query, self.module_options)
        normalized_query = query.strip()

        if reset_empty_groups and not normalized_query:
            set_module_tree_expansion(matches, self.executable_lookup, self.expanded_groups, False)
        elif normalized_query and normalized_query != self.last_query:
            set_module_tree_expansion(matches, self.executable_lookup, self.expanded_groups, True)

        self.last_query = normalized_query
        self.controls.module_suggestions_list.controls = build_module_suggestion_controls(
            matches,
            query,
            self.executable_lookup,
            self.expanded_groups,
            self.toggle_group,
            self.on_select_module,
        )
        self.controls.module_panel.visible = bool(matches)
        self.update_control(self.controls.module_panel)
        self.sync_stack()

    def show_argument_suggestions_from_event(self, e) -> None:
        # Exibe sugestoes de argumento usando o valor do input secundario.
        self.show_argument_suggestions(e.control.value or "")

    def show_argument_suggestions(self, query: str = "") -> None:
        # Busca e renderiza argumentos para o modulo selecionado.
        if self.selected_module_id is None:
            self.hide_argument_suggestions()
            self.update_control(self.controls.argument_panel)
            self.sync_stack()
            return

        arguments = self.search_arguments(self.selected_module_id, query)
        self.apply_argument_suggestions(arguments)

    def apply_argument_suggestions(
        self,
        arguments: Sequence[ui.argument_dropdown.ArgumentOption],
    ) -> None:
        if self.selected_module_id is None:
            return
        self.controls.argument_suggestions_list.controls = ui.argument_dropdown.build_argument_suggestion_controls(arguments, self.on_select_argument)
        self.controls.argument_panel.visible = self.selected_module_path is not None
        self.update_control(self.controls.argument_panel)
        self.sync_stack()

    def open_argument_dropdown(
        self,
        module_id: int,
        module_path: str,
        *,
        load_suggestions: bool = True,
    ) -> None:
        # Abre o dropdown secundario para escolher argumento do modulo.
        self.selected_module_id = module_id
        self.selected_module_path = module_path
        self.hide_module_suggestions()
        self.controls.argument_input_field.value = ""
        if load_suggestions:
            self.show_argument_suggestions("")
        else:
            self.controls.argument_suggestions_list.controls = [
                ft.Container(
                    height=80,
                    alignment=ft.Alignment.CENTER,
                    content=ft.ProgressRing(width=22, height=22, stroke_width=2),
                )
            ]
            self.controls.argument_panel.visible = True
        self.update_control(self.controls.argument_input_field)
        self.update_control(self.controls.module_panel)
        self.sync_stack()


def option_path(module_option: ModuleOption) -> str:
    # Extrai o caminho textual de uma opcao de modulo.
    if isinstance(module_option, str):
        return module_option
    return str(module_option.get("path", ""))


def option_is_executable(module_option: ModuleOption) -> bool:
    # Informa se a opcao de modulo representa um item executavel.
    if isinstance(module_option, str):
        return False
    return bool(module_option.get("is_executable", False))


def option_module_id(module_option: ModuleOption) -> int | None:
    if isinstance(module_option, str):
        return None
    value = module_option.get("module_id")
    return value if isinstance(value, int) else None


def option_command_paths(module_option: ModuleOption) -> list[str]:
    if isinstance(module_option, str):
        return [module_option]
    values = module_option.get("command_paths", ())
    paths = [str(value) for value in values] if isinstance(values, (list, tuple)) else []
    return list(dict.fromkeys([option_path(module_option), *paths]))


def sort_modules(module_options: Sequence[ModuleOption]) -> list[ModuleOption]:
    # Ordena modulos mantendo pais e filhos em uma ordem previsivel.
    return sorted(module_options, key=lambda module_option: _parent_sort_key(option_path(module_option)))


def filter_modules(query: str, module_options: Sequence[ModuleOption]) -> list[ModuleOption]:
    # Filtra os modulos pelo texto digitado no input principal.
    tokens = [token for token in ui.text_utils.normalize(query).split() if token]
    if not tokens:
        return sort_modules(module_options)

    matches = []
    for module_option in sort_modules(module_options):
        searchable_value = (
            option_path(module_option)
            if isinstance(module_option, str)
            else str(module_option.get("search_text", option_path(module_option)))
        )
        searchable = ui.text_utils.normalize(searchable_value)
        if all(_token_matches(token, searchable) for token in tokens):
            matches.append(module_option)

    return matches[:6]


def resolve_voice_module(
    query: str,
    module_options: Sequence[ModuleOption],
) -> tuple[str, str] | None:
    """Compatibilidade: devolve caminho e argumento quando a resolução é única."""
    resolved = resolve_voice_module_option(query, module_options)
    if resolved is None or resolved.ambiguous:
        return None
    return resolved.path, resolved.argument


def resolve_voice_module_option(
    query: str,
    module_options: Sequence[ModuleOption],
) -> ResolvedModule | None:
    """Resolve uma fala para um ID sem escolher silenciosamente entre ambiguidades."""
    original_words = [word for word in re.split(r"\s+", query.strip()) if word]
    normalized_words = [ui.text_utils.normalize(word).strip(".,!?;:") for word in original_words]
    candidates: list[tuple[int, int | None, str, str]] = []

    for module_option in module_options:
        if not option_is_executable(module_option):
            continue
        module_path = option_path(module_option)
        for command_path in option_command_paths(module_option):
            path_words = [
                word
                for word in ui.text_utils.normalize(command_path.replace("/", " ")).split()
                if word
            ]
            if len(path_words) > len(normalized_words):
                continue
            if normalized_words[: len(path_words)] != path_words:
                continue
            argument = " ".join(original_words[len(path_words):]).strip(" ,.!?;:")
            candidates.append(
                (
                    len(path_words),
                    option_module_id(module_option),
                    module_path,
                    argument,
                )
            )

    if not candidates:
        return None
    longest_match = max(candidate[0] for candidate in candidates)
    best_candidates = [candidate for candidate in candidates if candidate[0] == longest_match]
    unique_modules = {
        (candidate[1], candidate[2]): candidate
        for candidate in best_candidates
    }
    if len(unique_modules) > 1:
        return ResolvedModule(None, "", "", ambiguous=True)
    _, module_id, module_path, argument = next(iter(unique_modules.values()))
    return ResolvedModule(module_id, module_path, argument)


def resolve_typed_module(
    query: str,
    module_options: Sequence[ModuleOption],
) -> ResolvedModule | None:
    normalized_query = ui.text_utils.normalize(query.replace("/", " ")).strip()
    if not normalized_query:
        return None
    matches: dict[tuple[int | None, str], ModuleOption] = {}
    for module_option in module_options:
        if not option_is_executable(module_option):
            continue
        if any(
            ui.text_utils.normalize(path.replace("/", " ")).strip() == normalized_query
            for path in option_command_paths(module_option)
        ):
            matches[(option_module_id(module_option), option_path(module_option))] = module_option
    if not matches:
        return None
    if len(matches) > 1:
        return ResolvedModule(None, "", "", ambiguous=True)
    module_id, path = next(iter(matches))
    return ResolvedModule(module_id, path, "")


def module_executable_lookup(module_options: Sequence[ModuleOption]) -> dict[str, bool]:
    # Monta um mapa rapido entre caminho do modulo e status executavel.
    return {
        option_path(module_option): option_is_executable(module_option)
        for module_option in module_options
        if option_path(module_option)
    }


def build_dropdown_panel(content: ft.Control, on_click: Callable | None = None) -> ft.Container:
    # Cria o painel visual reutilizado pelos dropdowns da home.
    return ft.Container(
        visible=False,
        padding=ft.Padding(left=8, top=8, right=8, bottom=8),
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=18,
        shadow=ft.BoxShadow(blur_radius=18, color="#18000000", offset=ft.Offset(0, 8)),
        content=content,
        on_click=on_click,
    )


def build_dropdown_stack(module_panel: ft.Container, argument_panel: ft.Container, dropdown_height: int) -> ft.Stack:
    # Posiciona os dropdowns na mesma area, com argumentos renderizando por cima.
    top_offset = 10
    panel_height = dropdown_height - top_offset

    module_panel.top = top_offset
    module_panel.left = 0
    module_panel.right = 0
    module_panel.height = panel_height
    argument_panel.top = top_offset
    argument_panel.left = 0
    argument_panel.right = 0
    argument_panel.height = panel_height

    return ft.Stack(width=800, height=0, controls=[module_panel, argument_panel])


def build_module_suggestion_controls(
    matches: Sequence[ModuleOption],
    query: str,
    executable_lookup: Mapping[str, bool],
    expanded_groups: dict[str, bool],
    on_toggle: Callable[[str], None],
    on_select: Callable[[int, str], None],
) -> list[ft.Control]:
    # Cria os controles da lista de modulos a partir da arvore filtrada.
    controls: list[ft.Control] = []
    has_query = bool(query.strip())
    tree = build_module_tree(matches, executable_lookup)

    def append_nodes(nodes: Mapping[str, dict], depth: int = 0) -> None:
        # Adiciona recursivamente pastas e folhas da arvore de modulos.
        for key in sorted(nodes, key=ui.text_utils.normalize):
            node = nodes[key]
            children = node["children"]
            module_path = str(node["path"])
            is_executable = bool(node["is_executable"])
            module_id = node.get("module_id")

            if children:
                is_expanded = expanded_groups.get(module_path, has_query)
                controls.append(
                    _build_module_group_header(
                        str(node["label"]),
                        module_path,
                        is_expanded,
                        is_executable,
                        module_id,
                        on_toggle,
                        on_select,
                        indent=depth * 24,
                    )
                )

                if is_expanded:
                    append_nodes(children, depth + 1)
            else:
                controls.append(
                    _build_module_leaf(
                        module_id,
                        module_path,
                        on_select,
                        label=str(node["label"]),
                        is_executable=is_executable,
                        indent=depth * 24 + 28,
                    )
                )

    append_nodes(tree)
    return controls


def build_module_tree(
    module_options: Sequence[ModuleOption],
    executable_lookup: Mapping[str, bool],
) -> dict[str, dict]:
    # Transforma caminhos como A / B / C em uma arvore de modulos.
    root: dict[str, dict] = {}

    for module_option in sort_modules(module_options):
        module_path = option_path(module_option)
        parts = _split_module_path(module_path)
        branch = root
        current_parts: list[str] = []

        for part in parts:
            current_parts.append(part)
            current_path = " / ".join(current_parts)
            branch = branch.setdefault(
                part,
                {
                    "label": part,
                    "path": current_path,
                    "children": {},
                    "is_executable": executable_lookup.get(current_path, False),
                    "module_id": None,
                },
            )["children"]

        if parts:
            node = root
            for part in parts:
                current_node = node[part]
                node = current_node["children"]
            current_node["is_executable"] = option_is_executable(module_option)
            current_node["module_id"] = option_module_id(module_option)

    return root


def set_module_tree_expansion(
    matches: Sequence[ModuleOption],
    executable_lookup: Mapping[str, bool],
    expanded_groups: dict[str, bool],
    is_expanded: bool,
) -> None:
    # Marca todos os grupos da arvore filtrada como expandidos ou recolhidos.
    tree = build_module_tree(matches, executable_lookup)

    def set_nodes(nodes: Mapping[str, dict]) -> None:
        # Aplica o estado de expansao nos grupos filhos.
        for node in nodes.values():
            if node["children"]:
                expanded_groups[str(node["path"])] = is_expanded
                set_nodes(node["children"])

    set_nodes(tree)


def _token_matches(token: str, searchable: str) -> bool:
    # Compara um token digitado contra um texto pesquisavel.
    if token in searchable:
        return True
    if token.endswith("s") and token[:-1] in searchable:
        return True
    if token.endswith("m") and f"{token[:-1]}ns" in searchable:
        return True
    return False


def _parent_sort_key(module_path: str) -> tuple[str, str]:
    # Gera a chave de ordenacao que prioriza o primeiro nivel do caminho.
    parts = [part.strip() for part in module_path.split("/") if part.strip()]
    parent_name = parts[0] if parts else module_path
    return ui.text_utils.normalize(parent_name), ui.text_utils.normalize(module_path)


def _split_module_path(module_path: str) -> list[str]:
    # Divide um caminho de modulo em partes limpas.
    return [part.strip() for part in module_path.split("/") if part.strip()]


def _build_executable_suffix(is_executable: bool) -> ft.Control:
    # Cria o icone de seta exibido nos itens executaveis.
    return ft.Icon(
        icon=EXECUTABLE_SUFFIX_ICON,
        size=16,
        color=PASTEL_DARK_PURPLE,
        visible=is_executable,
    )


def _build_module_leaf(
    module_id: int | None,
    module_path: str,
    on_select: Callable[[int, str], None],
    label: str,
    is_executable: bool,
    indent: int = 0,
) -> ft.Container:
    # Cria uma linha de modulo sem filhos.
    return ft.Container(
        height=42,
        padding=ft.Padding(left=12 + indent, top=0, right=12, bottom=0),
        border_radius=12,
        ink=True,
        ink_color=PASTEL_BLUE,
        on_click=(
            (lambda _, selected_id=module_id, selected=module_path: on_select(selected_id, selected))
            if module_id is not None
            else None
        ),
        content=ft.Row(
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(icon=ft.Icons.ACCOUNT_TREE_ROUNDED, size=18, color=PASTEL_PURPLE),
                ft.Text(label, size=14, color=TEXT_PRIMARY, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True, expand=True),
                _build_executable_suffix(is_executable),
            ],
        ),
    )


def _build_module_group_header(
    label: str,
    module_path: str,
    is_expanded: bool,
    is_executable: bool,
    module_id: int | None,
    on_toggle: Callable[[str], None],
    on_select: Callable[[int, str], None],
    indent: int = 0,
) -> ft.Container:
    # Cria uma linha de modulo com filhos expansivel como pasta.
    controls: list[ft.Control] = [
        ft.Icon(
            icon=ft.Icons.KEYBOARD_ARROW_DOWN_ROUNDED if is_expanded else ft.Icons.KEYBOARD_ARROW_RIGHT_ROUNDED,
            size=20,
            color=PASTEL_DARK_PURPLE,
        ),
        ft.Icon(icon=ft.Icons.FOLDER_ROUNDED, size=18, color=PASTEL_PURPLE),
        ft.Text(label, size=14, weight=ft.FontWeight.W_700, color=TEXT_PRIMARY, overflow=ft.TextOverflow.ELLIPSIS, no_wrap=True, expand=True),
    ]

    if is_executable and module_id is not None:
        controls.append(
            ft.Container(
                width=28,
                height=28,
                border_radius=14,
                alignment=ft.Alignment.CENTER,
                ink=True,
                ink_color=PASTEL_BLUE,
                on_click=lambda _, selected_id=module_id, selected=module_path: on_select(selected_id, selected),
                content=ft.Icon(icon=EXECUTABLE_SUFFIX_ICON, size=16, color=PASTEL_DARK_PURPLE),
            )
        )

    return ft.Container(
        height=40,
        padding=ft.Padding(left=10 + indent, top=0, right=12, bottom=0),
        border_radius=12,
        ink=True,
        ink_color=PASTEL_BLUE,
        on_click=lambda _, selected=module_path: on_toggle(selected),
        content=ft.Row(spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER, controls=controls),
    )
