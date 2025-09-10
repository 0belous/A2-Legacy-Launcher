function pushIni{
    param(
        [string]$iniFile
    )
    .\android-sdk\platform-tools\adb.exe push $iniFile /data/local/tmp/Engine.ini
    $packageName = "com.AnotherAxiom.A2"
    $targetDir = "files/UnrealGame/A2/A2/Saved/Config/Android"

    $shellCommand = "run-as $packageName sh -c 'mkdir files 2>/dev/null; mkdir files/UnrealGame 2>/dev/null; mkdir files/UnrealGame/A2 2>/dev/null; mkdir files/UnrealGame/A2/A2 2>/dev/null; mkdir files/UnrealGame/A2/A2/Saved 2>/dev/null; mkdir files/UnrealGame/A2/A2/Saved/Config 2>/dev/null; mkdir $targetDir 2>/dev/null; cp /data/local/tmp/Engine.ini $targetDir/'"
    $result = .\android-sdk\platform-tools\adb.exe shell $shellCommand
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create directory or copy INI file. ADB output: $result"
    } else {
        Write-Host "[SUCCESS] INI file pushed successfully."
    }
}

Write-Host "[1] - Default: will work for most builds <-- Recommended"
Write-Host "[2] - Vegas: default level used in the vegas build"
Write-Host "[3] - Custom: provide a custom ini file"
$whichIni = Read-Host -Prompt "Enter 1-3 to pick which ini file to use (press enter for default)"
if($whichIni.Contains("1") -Or ($whichIni -eq '')){
    pushIni('./Engine.ini')
}elseif($whichIni.Contains("2")){
    pushIni('./EngineVegas.ini')
}elseif($whichIni.Contains("3")){
    $iniInput = Read-Host -Prompt "Drag and drop your ini file here"
    pushIni($iniInput)
}