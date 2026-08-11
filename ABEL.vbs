' Lanza ABEL sin ninguna ventana visible.
' pythonw ya evita la consola de Python, pero el proceso intermedio
' de Windows puede parpadear; esto lo elimina del todo.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = CreateObject("Scripting.FileSystemObject") _
    .GetParentFolderName(WScript.ScriptFullName)
shell.Run """ .venv\Scripts\pythonw.exe"" abel.py", 0, False