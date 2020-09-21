# mp-poraclePvpHelper
This MAD plugin exists to pass RDM-like PvP data to PoracleJS using webhooks. It targets the PvP Stats Tracking implementation in
[PoracleJS PR #151](https://github.com/KartulUdus/PoracleJS/pull/151) and complies with its formats.

## Installation
Pulling this directly into your MAD/plugins folder *may* cause issues until [MAD PR #1010](https://github.com/Map-A-Droid/MAD/pull/1010)
is merged. Downloading and distributing `.mp` files for an active project seems a little tedious to me though, so this will be the primary
way of distribution for this plugin. I may occasionally upload one as a release though.

After installation, the usual procedure for MAD plugins applies. Copy the `plugin.ini.example` to `plugin.ini` and edit it to your personal preferences.

It is recommended to deactivate regular pokemon webhooks to endpoint(s) you're sending to with this plugin, because it sends all the pokemon
data the usual webhook worker would send, enhanced with the additional pvp data. Sending the same data through two different webhook
workers may cause unintended behaviour. You can disable regular pokemon data either by disabling pokemon webhooks
altogether, or by omitting pokemon from the list of enabled webhook types for a specific URL (example: `[raid gym weather pokestop quest]http://localhost:4201`)

Finally, restart your MAD instance.

### First start
On first start, the required data for pvp rank/rating lookups will be calculated locally and saved to a `data.pickle` file. This will take a while.
Progress should be logged for every 50th mon-form combination. Subsequent starts will load the data from the `data.pickle` file.

## Re-calculation of data
To apply certain settings or load new Pokemon / Stats / Forms, a re-calculation of the previously mentioned data will be necessary. Settings that require a recalc
will be commented accordingly in the `plugin.ini.example` file.
To achieve a recalc, delete the `data.pickle` file and restart your MAD instance. A new initial calculation will start.

## Multi-instance setup
This plugin is able to run across multiple MAD instances from the same MAD directory. Settings can be made instance-specific by naming a settings category
like the `status-name` of your instances. An example can be seen as a comment in the `plugin.ini.example` file.

The `data.pickle` file can be shared across those instances, so only one initial calculation is required.

# A little disclaimer
I don't think it's the scanners job to provide this data. I think these are things that should happen in the front-end, like in
[PokeAlarm](https://github.com/pokealarm/pokealarm). However, I only speak python, so I'm unable to make a "correct" PR for PoracleJS. So instead
of complaining, I put my "beliefs" aside, accepted the status quo and created this MAD plugin which is basically a port and extension of the pvp work
I made for PokeAlarm.
