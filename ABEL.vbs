' Lanza ABEL sin ninguna ventana visible.
' pythonw ya evita la consola de Python, pero el proceso intermedio
' de Windows puede parpadear; esto lo elimina del todo.
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

raiz = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = raiz

shell.Run """" & raiz & "\.venv\Scripts\python.exe"" """ & raiz & "\abel.py""", 0, False