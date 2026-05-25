pytest -q

if (Test-Path "$PSScriptRoot\..\frontend\node_modules") {
    Push-Location "$PSScriptRoot\..\frontend"
    try {
        npm run typecheck
        npm run build
    }
    finally {
        Pop-Location
    }
}
