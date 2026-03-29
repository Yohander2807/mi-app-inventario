import flet as ft
import sqlite3
import os
import shutil
import sys

# --- CONFIGURACIÓN DE BASE DE DATOS (FIX PARA ANDROID) ---
def get_db_connection():
    # Determinamos la ruta de almacenamiento según el OS
    if os.name == 'nt':  # Windows
        base_path = os.getenv('APPDATA')
    else:  # Android / Linux
        # En Android, 'HOME' apunta al directorio interno de la App
        base_path = os.environ.get("HOME", os.path.expanduser("~"))
        # Nos aseguramos de entrar en la carpeta de archivos de la App
        if not base_path.endswith("files"):
            base_path = os.path.join(base_path, "files")

    data_dir = os.path.join(base_path, "sopsoft_erp")
    
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    
    db_path = os.path.join(data_dir, "database.db")
    
    # Lógica de despliegue: Si la DB no existe en la carpeta de escritura, la traemos de assets
    if not os.path.exists(db_path):
        # Ruta donde Flet guarda los assets empaquetados
        source_db = os.path.join(os.path.dirname(__file__), "data", "database.db")
        
        if os.path.exists(source_db):
            shutil.copy(source_db, db_path)
            # Damos permisos explicitos en Android (777) por si acaso
            if os.name != 'nt':
                os.chmod(db_path, 0o777)

    conn = sqlite3.connect(db_path)
    # Optimizaciones para evitar bloqueos en móviles (WAL Mode)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA synchronous=NORMAL;')
    conn.execute('PRAGMA foreign_keys = ON;')
    conn.row_factory = sqlite3.Row
    return conn

def main(page: ft.Page):
    page.title = "SOPSoft ERP - Sistema de Inventario"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0f0f0f"
    # Padding superior para evitar el notch/barra de estado en Android
    page.padding = ft.padding.only(top=55, left=15, right=15, bottom=20)

    tasa_actual = 36.50

    # --- ELEMENTOS DE UI ---
    lista_productos = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    lista_marcas = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    text_tasa_header = ft.Text("36.50 Bs", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)

    # --- LÓGICA DE DATOS ---
    def obtener_tasa():
        nonlocal tasa_actual
        try:
            conn = get_db_connection()
            tasa_row = conn.execute("SELECT tasa_dia FROM configuracion LIMIT 1").fetchone()
            tasa_actual = float(tasa_row['tasa_dia']) if tasa_row else 36.50
            conn.close()
        except: tasa_actual = 36.50
        text_tasa_header.value = f"{tasa_actual} Bs"
        page.update()

    def obtener_marcas():
        try:
            conn = get_db_connection()
            marcas = conn.execute("SELECT * FROM marca ORDER BY nombre ASC").fetchall()
            conn.close()
            return marcas
        except: return []

    def obtener_productos(search=""):
        try:
            conn = get_db_connection()
            query = """
                SELECT p.id, p.nombre, m.nombre AS marca, p.marca_id, p.precio as precio_usd, p.precio_bs 
                FROM producto p LEFT JOIN marca m ON p.marca_id = m.id 
                WHERE p.nombre LIKE ? OR m.nombre LIKE ?
                ORDER BY p.id DESC
            """
            search_val = f"%{search}%"
            productos = conn.execute(query, (search_val, search_val)).fetchall()
            conn.close()
            return productos
        except: return []

    def refrescar_vistas(e=None):
        lista_productos.controls.clear()
        marcas = obtener_marcas()
        dd_marca.options = [ft.dropdown.Option(key=str(m['id']), text=m['nombre']) for m in marcas]
        
        for p in obtener_productos(search_bar.value):
            p_usd = float(p['precio_usd'] or 0)
            p_bs_fijo = float(p['precio_bs'] or 0)
            display_usd = f"${p_usd:.2f}"
            display_bs = f"{(p_usd * tasa_actual):.2f} Bs" if p_usd > 0 else f"{p_bs_fijo:.2f} Bs"

            lista_productos.controls.append(ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(p['nombre'], weight=ft.FontWeight.BOLD, size=16),
                        ft.Text(p['marca'] or "Genérico", size=12, color=ft.Colors.GREY)
                    ], expand=True),
                    ft.Column([
                        ft.Text(display_usd, color=ft.Colors.GREEN, weight=ft.FontWeight.BOLD),
                        ft.Text(display_bs, size=11, color=ft.Colors.BLUE_200 if p_usd == 0 else ft.Colors.WHITE)
                    ], horizontal_alignment=ft.CrossAxisAlignment.END),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda _, x=p: abrir_editar_prod(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, on_click=lambda _, id=p['id']: eliminar_logic("producto", id))
                ]), padding=15, bgcolor="#161616", border_radius=12, border=ft.border.all(1, "#252525")
            ))

        lista_marcas.controls.clear()
        for m in marcas:
            lista_marcas.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SELL_ROUNDED, color=ft.Colors.AMBER),
                    ft.Text(m['nombre'], weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=lambda _, x=m: abrir_editar_marca(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, on_click=lambda _, id=m['id']: eliminar_logic("marca", id))
                ]), padding=12, bgcolor="#161616", border_radius=10
            ))
        page.update()

    # --- MODALES ---
    def cerrar_modal(e):
        modal_tasa.open = modal_marca.open = modal_producto.open = False
        page.update()

    txt_nueva_tasa = ft.TextField(label="Nueva Tasa (Bs)", prefix="Bs ", keyboard_type=ft.KeyboardType.NUMBER)
    modal_tasa = ft.AlertDialog(
        title=ft.Text("Actualizar Tasa"), content=txt_nueva_tasa,
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modal), ft.ElevatedButton("Actualizar", on_click=lambda _: guardar_tasa())]
    )

    def guardar_tasa():
        if txt_nueva_tasa.value:
            conn = get_db_connection()
            conn.execute("UPDATE configuracion SET tasa_dia = ?", (float(txt_nueva_tasa.value),))
            conn.commit(); conn.close(); obtener_tasa(); cerrar_modal(None); refrescar_vistas()

    edit_marca_id = ft.Text(""); txt_nombre_marca = ft.TextField(label="Nombre de la Marca")
    modal_marca = ft.AlertDialog(
        title=ft.Text("Gestionar Marca"), content=txt_nombre_marca,
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modal), ft.ElevatedButton("Guardar", on_click=lambda _: guardar_marca_logic())]
    )

    def guardar_marca_logic():
        if txt_nombre_marca.value:
            conn = get_db_connection()
            if edit_marca_id.value: conn.execute("UPDATE marca SET nombre=? WHERE id=?", (txt_nombre_marca.value, edit_marca_id.value))
            else: conn.execute("INSERT INTO marca (nombre) VALUES (?)", (txt_nombre_marca.value,))
            conn.commit(); conn.close(); cerrar_modal(None); refrescar_vistas()

    edit_prod_id = ft.Text(""); txt_prod_nombre = ft.TextField(label="Nombre")
    dd_marca = ft.Dropdown(label="Marca")
    txt_prod_precio_usd = ft.TextField(label="Precio ($)", expand=True, prefix="$ ")
    txt_prod_precio_bs = ft.TextField(label="Precio (Bs)", expand=True, prefix="Bs ")

    modal_producto = ft.AlertDialog(
        title=ft.Text("Gestionar Producto"),
        content=ft.Column([
            txt_prod_nombre, dd_marca, 
            ft.Text("Si usas $, el precio en Bs es dinámico.", size=11, color=ft.Colors.GREY),
            ft.Row([txt_prod_precio_usd, txt_prod_precio_bs])
        ], tight=True, spacing=15),
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modal), ft.ElevatedButton("Guardar", on_click=lambda _: guardar_producto_logic())]
    )

    def guardar_producto_logic():
        if txt_prod_nombre.value and dd_marca.value:
            usd = float(txt_prod_precio_usd.value or 0); bs = float(txt_prod_precio_bs.value or 0)
            conn = get_db_connection()
            if edit_prod_id.value: 
                conn.execute("UPDATE producto SET nombre=?, marca_id=?, precio=?, precio_bs=? WHERE id=?", (txt_prod_nombre.value, dd_marca.value, usd, bs, edit_prod_id.value))
            else: 
                conn.execute("INSERT INTO producto (nombre, marca_id, precio, precio_bs) VALUES (?, ?, ?, ?)", (txt_prod_nombre.value, dd_marca.value, usd, bs))
            conn.commit(); conn.close(); cerrar_modal(None); refrescar_vistas()

    def abrir_editar_prod(p):
        edit_prod_id.value = str(p['id']); txt_prod_nombre.value = p['nombre']; dd_marca.value = str(p['marca_id'])
        txt_prod_precio_usd.value = str(p['precio_usd']); txt_prod_precio_bs.value = str(p['precio_bs'])
        modal_producto.open = True; page.update()

    def abrir_editar_marca(m):
        edit_marca_id.value = str(m['id']); txt_nombre_marca.value = m['nombre']
        modal_marca.open = True; page.update()

    def eliminar_logic(tabla, id):
        conn = get_db_connection()
        try:
            conn.execute(f"DELETE FROM {tabla} WHERE id=?", (id,))
            conn.commit()
        except:
            page.snack_bar = ft.SnackBar(ft.Text("Elemento en uso")); page.snack_bar.open = True
        conn.close(); refrescar_vistas()

    # --- UI PRINCIPAL ---
    header = ft.Row([
        ft.Column([
            ft.Text("SOPSoft ERP", size=20, weight=ft.FontWeight.BOLD),
            ft.Text("Inventario", size=12, color=ft.Colors.BLUE_200),
        ], spacing=0),
        ft.Container(
            content=text_tasa_header, padding=ft.padding.symmetric(10, 20),
            bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.BLUE), border=ft.border.all(1, ft.Colors.BLUE_900),
            border_radius=12, on_click=lambda _: setattr(modal_tasa, "open", True) or page.update()
        )
    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    search_bar = ft.TextField(hint_text="Buscar...", prefix_icon=ft.Icons.SEARCH, on_change=refrescar_vistas, border_radius=12, bgcolor="#161616")

    tabs_control = ft.Tabs(
        selected_index=0, expand=True, length=2,
        content=ft.Column(
            expand=True,
            controls=[
                ft.TabBar(tabs=[
                    ft.Tab(label="Productos", icon=ft.Icons.SHOPPING_BAG),
                    ft.Tab(label="Marcas", icon=ft.Icons.SELL),
                ]),
                ft.TabBarView(
                    expand=True,
                    controls=[
                        ft.Column([ft.Divider(height=10, color=ft.Colors.TRANSPARENT), search_bar, lista_productos], expand=True),
                        ft.Column([ft.Divider(height=10, color=ft.Colors.TRANSPARENT), lista_marcas], expand=True),
                    ]
                )
            ]
        )
    )

    page.floating_action_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD, bgcolor=ft.Colors.BLUE, 
        on_click=lambda _: abrir_modal_nuevo(None)
    )

    def abrir_modal_nuevo(e):
        if tabs_control.selected_index == 0:
            edit_prod_id.value = ""; txt_prod_nombre.value = ""; dd_marca.value = None
            txt_prod_precio_usd.value = ""; txt_prod_precio_bs.value = ""; modal_producto.open = True
        else:
            edit_marca_id.value = ""; txt_nombre_marca.value = ""; modal_marca.open = True
        page.update()

    page.overlay.extend([modal_tasa, modal_marca, modal_producto])
    page.add(header, ft.Divider(height=10, color=ft.Colors.TRANSPARENT), tabs_control)
    
    obtener_tasa(); refrescar_vistas()

if __name__ == "__main__":
    ft.app(target=main)