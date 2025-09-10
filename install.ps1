function fileDrop-Parser{
    param (
        [Parameter(Mandatory=$true)]
        [string]$RawPath
    )
    $pathWithoutOperator = $RawPath -replace '^& '
    $cleanedPath = $pathWithoutOperator.Trim("`"'")
    return $cleanedPath
}

Write-Host "Download commandline tools: https://dl.google.com/android/repository/commandlinetools-win-13114758_latest.zip"
$cmdtoolsPath = fileDrop-Parser((Read-Host -Prompt "Drag and drop the downloaded file here"))
if(Test-Path $cmdtoolsPath){
    Remove-Item -Path "./android-sdk" -Recurse > $null
    mkdir android-sdk
    Expand-Archive -Path $cmdtoolsPath "./android-sdk/"
    ./android-sdk/cmdline-tools/bin/sdkmanager.bat --sdk_root=./android-sdk "build-tools;34.0.0"
    ./android-sdk/cmdline-tools/bin/sdkmanager.bat --sdk_root=./android-sdk "platform-tools"
}else{
    Write-Host "Unknown file"
}
