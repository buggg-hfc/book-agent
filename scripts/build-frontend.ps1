Push-Location "$PSScriptRoot\..\frontend"
try {
    npm install
    npm run typecheck
    npm run build
}
finally {
    Pop-Location
}
