Set shell = CreateObject("WScript.Shell")
scriptPath = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))
command = "sync"
If WScript.Arguments.Count > 0 Then command = WScript.Arguments(0)
If command <> "sync" And command <> "--help" Then WScript.Quit 2
shell.Run """" & scriptPath & "Sync.cmd"" " & command, 0, False
