param(
    [int]$Port = 8000,
    [string]$HostName = "127.0.0.1"
)

$env:BOOK_AGENT_HOST = $HostName
$env:BOOK_AGENT_PORT = "$Port"
python -m book_agent.server
