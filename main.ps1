param (
[string]$ini,
[string]$apk,
[string]$obb
)

# Orion Drift Legacy Launcher by Obelous

if(!(Test-Path ./android-sdk/licenses/android-sdk-license)){
    Write-Host "Android SDK not found, please run install.ps1"
    exit
}else{
    Write-Host "[INFO] Android SDK found"
}

if(!(Get-Command java -ErrorAction SilentlyContinue)){
    Write-Host "[ERROR] Java not found in path"
}else{
    Write-Host "[INFO] Java detected"
}

$env:KEYSTORE_PASSWORD = "com.AnotherAxiom.A2"
$output = .\android-sdk\platform-tools\adb.exe devices | Where-Object { $_ -ne '' }
$connectedDevices = $output | Select-Object -Skip 1 | Where-Object { $_ -match "device" -and $_ -notmatch "unauthorized" }

Remove-Item -Path "./tmp" -Recurse > $null
mkdir ./tmp > $null

function uploadOBB{
    param(
        [string]$obbFile
    )
    $destinationDir = "/sdcard/Android/obb/com.AnotherAxiom.A2/"
    .\android-sdk\platform-tools\adb.exe shell "mkdir -p $destinationDir"
    Write-Host "[INFO] Uploading OBB file..."
    .\android-sdk\platform-tools\adb.exe push $obbFile $destinationDir
}
    
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

function fileDrop-Parser{
    param (
        [Parameter(Mandatory=$true)]
        [string]$RawPath
    )
    $pathWithoutOperator = $RawPath -replace '^& '
    $cleanedPath = $pathWithoutOperator.Trim("`"'")
    return $cleanedPath
}

if($connectedDevices.Count -eq 1){
    Write-Host "[SUCCESS] Found exactly one ADB device, assuming it's a VR headset";
    # If apk paramter is used, preset the path and ini
    if($apk){
        $apkPath = $apk
    }else{
        $apkPath = fileDrop-Parser((Read-Host -Prompt "Drag and drop the APK you want to use onto this terminal"))
    }
    $apkExists = Test-Path $apkPath
    if($apkPath.Contains(".apk") -And $apkExists){
    Write-Host "[SUCCESS] Found APK"
    Write-Host "[INFO] Decompiling"
    # Java apktool decompile from source $apkPath output to tmp/decompiled
    &java -jar "./apktool_2.12.0.jar" d -s $apkPath -o ./tmp/decompiled
    Write-Host "[INFO] Compiling"
    # Java apktool compile tmp/decompiled -enable debug -output to compiled.apk
    &java -jar "./apktool_2.12.0.jar" b ./tmp/decompiled -d -o ./tmp/compiled.apk
    Write-Host "[INFO] Aligning"
    &"./android-sdk/build-tools/34.0.0/zipalign.exe" -v 4 ./tmp/compiled.apk ./tmp/compiled.aligned.apk > $null
    Write-Host "[INFO] Signing"
    # Sign with dev.keystore and password defined at the top
    &"./android-sdk/build-tools/34.0.0/apksigner.bat" sign --ks dev.keystore --ks-pass env:KEYSTORE_PASSWORD --out ./tmp/compiled.aligned.signed.apk ./tmp/compiled.aligned.apk
    Write-Host "[INFO] Uninstalling A2"
    &.\android-sdk\platform-tools\adb.exe uninstall com.AnotherAxiom.A2
    Write-Host "[INFO] Installing Modified APK"
    &.\android-sdk\platform-tools\adb.exe install -r ./tmp/compiled.aligned.signed.apk
    if($obb){
        $obbPath = $obb
    }else{
        $obbPath = fileDrop-Parser((Read-Host -Prompt "Drag and drop the OBB you want to use onto this terminal, or press enter to skip"))
    }
    if(($obbPath.Contains(".obb")) -And (Test-Path $obbPath)){
        Write-Host "[SUCCESS] Found OBB"
        uploadOBB($obbPath)
    } elseif($obbPath.Length -eq 0){
        Write-Host "[INFO] Skipping OBB upload"
    } else{
        Write-Host "[ERROR] OBB file not found"
    }
    if(!$ini){
        Write-Host "[1] - Default: will work for most builds <-- Recommended"
        Write-Host "[2] - Vegas: default level used in the vegas build"
        Write-Host "[3] - Custom: provide a custom ini file"
        $whichIni = (Read-Host -Prompt "Enter 1-3 to pick which ini file to use (press enter for default)")
        if($whichIni.Contains("1") -Or ($whichIni -eq '')){
            pushIni('./Engine.ini')
        }elseif($whichIni.Contains("2")){
            pushIni('./EngineVegas.ini')
        }elseif($whichIni.Contains("3")){
            $iniInput = fileDrop-Parser((Read-Host -Prompt "Drag and drop your ini file here"))
            pushIni($iniInput)
        } else{
            Write-Host "Enter a valid option or file"
        }
    }else{
        pushIni($ini)
    }
    Write-Host "[DONE] Launch the game, run maintain.ps1 before every subsequent launch!"
    }else{
        Write-Host "[ERROR] Not an APK file or file doesn't exist"
    }
}else{
    Write-Host "[ERROR] Check headset for authorization prompt and make sure it's the only one connected"
}
