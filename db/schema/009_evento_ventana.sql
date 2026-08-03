INSERT INTO event_types (name, description) VALUES
    ('window_session',
     'Sesión de uso de una aplicación en primer plano, con su duración. '
     'Observación: refleja qué ventana tuvo el foco, no qué hacía el usuario. '
     'reason indica cómo terminó: cambio, parcial, sin_foco o fragmentada.');