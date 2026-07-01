for ($i = 1; $i -le 12; $i++) {
    try {
        Invoke-WebRequest `
            -Uri "http://localhost:5000/submit" `
            -Method POST `
            -ContentType "application/json" `
            -Body '{"text":"This is a test submission for rate limit testing purposes only.","creator_id":"ratelimit-test"}' `
            -UseBasicParsing | ForEach-Object { $_.StatusCode }
    }
    catch {
        $_.Exception.Response.StatusCode.value__
    }
}
