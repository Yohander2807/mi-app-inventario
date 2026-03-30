import flet as ft
import sqlite3
import os

# --- CONFIGURACIÓN DE BASE DE DATOS PERSISTENTE ---
def get_db_connection():
    # Buscamos la ruta de datos del sistema (App Storage) para Android/iOS
    # Si no existe (estamos en PC), usamos una ruta local relativa.
    data_dir = os.getenv("FLET_APP_STORAGE_DATA")
    
    if data_dir:
        # Ruta Segura para Móvil (APK/iOS)
        db_path = os.path.join(data_dir, "database.db")
    else:
        # Ruta para Desarrollo en PC
        db_path = os.path.join(os.path.dirname(__file__), "database.db")

    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.execute('PRAGMA foreign_keys = ON;')
    
    # --- INICIALIZACIÓN DE TABLAS (Crucial para el primer inicio en móvil) ---
    conn.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            tasa_dia REAL DEFAULT 36.50
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS marca (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS producto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            marca_id INTEGER,
            precio REAL DEFAULT 0,
            precio_bs REAL DEFAULT 0,
            FOREIGN KEY (marca_id) REFERENCES marca(id)
        )
    """)
    
    # Insertar tasa inicial si la tabla está vacía
    if not conn.execute("SELECT 1 FROM configuracion").fetchone():
        conn.execute("INSERT INTO configuracion (id, tasa_dia) VALUES (1, 36.50)")
        conn.commit()

    conn.row_factory = sqlite3.Row
    return conn

def main(page: ft.Page):
    page.title = "SOPSoft ERP"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = "#0f0f0f"
    page.padding = 20

    # Configuración de ventana para desktop (no afecta al móvil)
    page.window.width = 450
    page.window.height = 800

    tasa_actual = 36.50

    # --- ELEMENTOS DE UI ---
    lista_productos = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    lista_marcas = ft.Column(spacing=10, scroll=ft.ScrollMode.ADAPTIVE, expand=True)
    text_tasa_header = ft.Text("Cargando...", size=16, weight="bold", color="white")

    # --- FUNCIONES DE LÓGICA ---
    def obtener_tasa():
        nonlocal tasa_actual
        try:
            conn = get_db_connection()
            tasa_row = conn.execute("SELECT tasa_dia FROM configuracion WHERE id=1").fetchone()
            tasa_actual = float(tasa_row['tasa_dia']) if tasa_row else 36.50
            conn.close()
        except: tasa_actual = 36.50
        text_tasa_header.value = f"{tasa_actual} Bs"
        page.update()

    def obtener_marcas():
        conn = get_db_connection()
        marcas = conn.execute("SELECT * FROM marca ORDER BY nombre ASC").fetchall()
        conn.close()
        return marcas

    def obtener_productos(search=""):
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

    def refrescar_vistas(e=None):
        lista_productos.controls.clear()
        marcas = obtener_marcas()
        dd_marca.options = [ft.dropdown.Option(key=str(m['id']), text=m['nombre']) for m in marcas]
        
        for p in obtener_productos(search_bar.value):
            p_usd = float(p['precio_usd'] or 0)
            p_bs_fijo = float(p['precio_bs'] or 0)
            
            # Lógica: USD manda si es > 0. Si no, muestra el BS fijo.
            display_usd = f"${p_usd:.2f}"
            display_bs = f"{(p_usd * tasa_actual):.2f} Bs" if p_usd > 0 else f"{p_bs_fijo:.2f} Bs"

            lista_productos.controls.append(ft.Container(
                content=ft.Row([
                    ft.Column([
                        ft.Text(p['nombre'], weight="bold", size=16),
                        ft.Text(p['marca'] or "Genérico", size=12, color="grey")
                    ], expand=True, spacing=2),
                    ft.Column([
                        ft.Text(display_usd, color="green", weight="bold"),
                        ft.Text(display_bs, size=11, color="blue200" if p_usd == 0 else "white")
                    ], horizontal_alignment="end", spacing=0),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_size=18, on_click=lambda _, x=p: abrir_editar_prod(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18, icon_color="red400", on_click=lambda _, id=p['id']: eliminar_logic("producto", id))
                ]), padding=15, bgcolor="#161616", border_radius=12, border=ft.border.all(1, "#252525")
            ))

        lista_marcas.controls.clear()
        for m in marcas:
            lista_marcas.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.SELL_ROUNDED, color="amber", size=20),
                    ft.Text(m['nombre'], weight="bold", expand=True),
                    ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_size=18, on_click=lambda _, x=m: abrir_editar_marca(x)),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18, icon_color="red400", on_click=lambda _, id=m['id']: eliminar_logic("marca", id))
                ]), padding=12, bgcolor="#161616", border_radius=10
            ))
        page.update()

    # --- MODALES ---
    def cerrar_modal(e):
        modal_tasa.open = False; modal_marca.open = False; modal_producto.open = False
        page.update()

    # Modal Tasa
    txt_nueva_tasa = ft.TextField(label="Nueva Tasa (Bs)", prefix_text="Bs ", keyboard_type=ft.KeyboardType.NUMBER)
    modal_tasa = ft.AlertDialog(title=ft.Text("Actualizar Tasa"), content=txt_nueva_tasa,
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modal), ft.ElevatedButton("Actualizar", on_click=lambda _: guardar_tasa())])

    def guardar_tasa():
        if txt_nueva_tasa.value:
            conn = get_db_connection()
            conn.execute("UPDATE configuracion SET tasa_dia = ? WHERE id=1", (float(txt_nueva_tasa.value),))
            conn.commit(); conn.close(); obtener_tasa(); cerrar_modal(None); refrescar_vistas()

    # Modal Marcas
    edit_marca_id = ft.Text(""); txt_nombre_marca = ft.TextField(label="Nombre de la Marca")
    modal_marca = ft.AlertDialog(title=ft.Text("Gestionar Marca"), content=txt_nombre_marca,
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modal), ft.ElevatedButton("Guardar", on_click=lambda _: guardar_marca_logic())])

    def guardar_marca_logic():
        if txt_nombre_marca.value:
            conn = get_db_connection()
            if edit_marca_id.value: conn.execute("UPDATE marca SET nombre=? WHERE id=?", (txt_nombre_marca.value, edit_marca_id.value))
            else: conn.execute("INSERT INTO marca (nombre) VALUES (?)", (txt_nombre_marca.value,))
            conn.commit(); conn.close(); cerrar_modal(None); refrescar_vistas()

    # Modal Productos
    edit_prod_id = ft.Text(""); txt_prod_nombre = ft.TextField(label="Nombre")
    dd_marca = ft.Dropdown(label="Marca")
    txt_prod_precio_usd = ft.TextField(label="Precio ($) - Dinámico", expand=True, prefix_text="$ ")
    txt_prod_precio_bs = ft.TextField(label="Precio (Bs) - Fijo", expand=True, prefix_text="Bs ")

    modal_producto = ft.AlertDialog(
        title=ft.Text("Gestionar Producto"),
        content=ft.Column([
            txt_prod_nombre, dd_marca,
            ft.Text("Define solo un tipo de precio o ambos.", size=10, color="grey"),
            ft.Row([txt_prod_precio_usd, txt_prod_precio_bs])
        ], tight=True, spacing=15),
        actions=[ft.TextButton("Cancelar", on_click=cerrar_modal), ft.ElevatedButton("Guardar", on_click=lambda _: guardar_producto_logic())]
    )

    def guardar_producto_logic():
        if txt_prod_nombre.value and dd_marca.value:
            usd = float(txt_prod_precio_usd.value or 0)
            bs = float(txt_prod_precio_bs.value or 0)
            conn = get_db_connection()
            if edit_prod_id.value: 
                conn.execute("UPDATE producto SET nombre=?, marca_id=?, precio=?, precio_bs=? WHERE id=?", 
                             (txt_prod_nombre.value, dd_marca.value, usd, bs, edit_prod_id.value))
            else: 
                conn.execute("INSERT INTO producto (nombre, marca_id, precio, precio_bs) VALUES (?, ?, ?, ?)", 
                             (txt_prod_nombre.value, dd_marca.value, usd, bs))
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
            page.snack_bar = ft.SnackBar(ft.Text("Vínculo activo detectado")); page.snack_bar.open = True
        conn.close(); refrescar_vistas()

    # --- HEADER DASHBOARD ---
    header = ft.Container(
        content=ft.Row([
            ft.Column([
                ft.Text("SOPSoft ERP", size=22, weight="bold", color="white"),
                ft.Text("Inventario & Precios", size=12, color="blue200"),
            ], spacing=0),
            ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CURRENCY_EXCHANGE_ROUNDED, size=18, color="white"),
                    text_tasa_header,
                ], spacing=8),
                padding=ft.padding.symmetric(10, 15),
                bgcolor=ft.Colors.with_opacity(0.15, "blue"),
                border_radius=12,
                on_click=lambda _: setattr(modal_tasa, "open", True) or page.update(),
                ink=True
            )
        ], alignment="spaceBetween"),
        margin=ft.margin.only(bottom=10)
    )

    search_bar = ft.TextField(
        hint_text="Buscar productos...", 
        prefix_icon=ft.Icons.SEARCH, 
        on_change=refrescar_vistas,
        border_radius=15,
        bgcolor="#161616",
        border_color="#252525"
    )

    tabs_control = ft.Tabs(
        selected_index=0,
        length=2,
        expand=True,
        tabs=[
            ft.Tab(text="Productos", icon=ft.Icons.INVENTORY_2_ROUNDED, 
                   content=ft.Column([ft.Divider(height=10, color="transparent"), search_bar, lista_productos], expand=True)),
            ft.Tab(text="Marcas", icon=ft.Icons.SELL_ROUNDED, 
                   content=ft.Column([ft.Divider(height=10, color="transparent"), lista_marcas], expand=True)),
        ]
    )

    def abrir_modal_nuevo():
        if tabs_control.selected_index == 0:
            edit_prod_id.value = ""; txt_prod_nombre.value = ""; dd_marca.value = None
            txt_prod_precio_usd.value = ""; txt_prod_precio_bs.value = ""; modal_producto.open = True
        else:
            edit_marca_id.value = ""; txt_nombre_marca.value = ""; modal_marca.open = True
        page.update()

    page.floating_action_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD, bgcolor="blue", on_click=lambda _: abrir_modal_nuevo()
    )

    page.overlay.extend([modal_tasa, modal_marca, modal_producto])
    page.add(header, tabs_control)
    
    obtener_tasa()
    refrescar_vistas()

if __name__ == "__main__":
    ft.app(target=main)