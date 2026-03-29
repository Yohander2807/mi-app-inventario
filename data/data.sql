CREATE TABLE marca (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- En SQLite es INTEGER, no INT
    nombre TEXT NOT NULL UNIQUE            -- Usamos TEXT en lugar de VARCHAR
);

CREATE TABLE producto (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL UNIQUE,
    marca_id INTEGER,
    precio REAL NOT NULL,                  -- REAL es el equivalente a FLOAT
    FOREIGN KEY(marca_id) REFERENCES marca(id) 
        ON UPDATE CASCADE 
        ON DELETE RESTRICT                 -- Corregido 'UPADTE' y 'RESTING'
);

CREATE TABLE configuracion (
    -- SQLite no tiene tipo ENUM. Usamos TEXT con un CHECK para simularlo.
    tema TEXT NOT NULL DEFAULT 'dark' CHECK (tema IN ('light', 'dark')),
    tasa_dia REAL NOT NULL
);

-- 1. Tabla de Cabecera de Factura
CREATE TABLE factura (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATETIME DEFAULT CURRENT_TIMESTAMP,
    total REAL NOT NULL DEFAULT 0.0
);

-- 2. Tabla de Detalle de Factura (Relaciona productos con facturas)
CREATE TABLE detalle_factura (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    factura_id INTEGER NOT NULL,
    producto_id INTEGER NOT NULL,
    cantidad INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario REAL NOT NULL, -- Guardamos el precio del momento de la venta
    subtotal REAL NOT NULL,
    FOREIGN KEY(factura_id) REFERENCES factura(id) ON DELETE CASCADE,
    FOREIGN KEY(producto_id) REFERENCES producto(id)
);


-- CONSULTA PARA OBTENER PRODUCTOS POR MARCA --

SELECT 
    p.nombre AS nombre_producto, 
    m.nombre AS nombre_marca, 
    p.precio
FROM producto p
LEFT JOIN marca m ON p.marca_id = m.id;