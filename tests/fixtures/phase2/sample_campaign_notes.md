# Otari Campaign Snapshot

## Location: Otari
- Key: otari
- Summary: A foggy fishing town on the Isle of Kortos.
- Type: settlement
- Region: Isle of Kortos
- Environment: coastal

## Faction: Dawnwatch
- Key: dawnwatch
- Summary: A vigilant local watch dedicated to protecting the harbor.
- Category: militia
- Goals: Keep Otari safe from smugglers and swamp threats.
- Influence: local
- Alignment: lawful good

## NPC: Captain Mira
- Key: captain-mira
- Summary: A veteran guard captain who knows every dockworker by name.
- Role: Guard Captain
- Disposition: cautious
- Goal: Keep the town prepared for danger.
- Appearance: Weathered armor and a sea-blue cloak.

## Event: Fishery Festival
- Key: fishery-festival
- Summary: An annual celebration that brings travelers and trouble alike.
- Event Date: 4724-05-12
- Phase: upcoming
- Details: Merchants, sailors, and thieves all crowd the harbor district.

## Relationships
| from | type | to | note |
| --- | --- | --- | --- |
| captain-mira | located_in | otari | She commands the waterfront barracks. |
| dawnwatch | headquartered_in | otari | The watch uses the old signal tower. |
| captain-mira | leads | dawnwatch | Mira answers to the town council. |
| fishery-festival | occurs_at | otari | The harbor will be packed. |
