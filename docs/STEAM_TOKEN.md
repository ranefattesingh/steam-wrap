# Getting a Steam access token

Every authenticated endpoint needs the **user's Steam access token**: the JWT
Steam issues to a logged-in user. The API reads the user's SteamID from the
token, so nothing else needs to be sent.

## Option 1: from the Steam store (quickest)

1. Log in at <https://store.steampowered.com> in your browser.
2. Open <https://store.steampowered.com/pointssummary/ajaxgetasyncconfig>.
3. Copy the value of `data.webapi_token`. It looks like
   `eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJyOnN0ZWFtIiwic3ViIjoiNzY1...`

The token expires after about a day. Fetch a new one when the API returns
`401 invalid_token` / `steam_auth_failed`.

## Option 2: your own login flow

Applications that sign users in through Steam's `IAuthenticationService`
receive an `access_token` the same way. Pass that token to this API.

## Sending it

```http
GET /api/v1/games
Authorization: Bearer eyJhbGciOi...
```

You can also use `?access_token=...` while `app.allow_query_token` is `true`
(the default for development). **Turn that off in production**, because URLs
end up in proxy logs and browser history.

## Privacy notes

* The token is a credential for that Steam account. Treat it like a password.
* This service never logs it. Query-string and `Authorization` values are
  redacted from every log line.
* Libraries are cached under a SHA-256 hash of the token, never under the
  SteamID, so a forged token can't read anyone's cached data.
* If the profile's **Game details** privacy setting is not public, Steam may
  return an empty library even with a valid token.
