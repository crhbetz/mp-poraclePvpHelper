# mp-poraclePvpHelper
This MAD plugin exists to pass RDM-like PvP data to PoracleJS using webhooks. It targets the PvP Stats Tracking implementation in the now merged
[PoracleJS PR #151](https://github.com/KartulUdus/PoracleJS/pull/151) / [PR #206](https://github.com/KartulUdus/PoracleJS/pull/206)
and complies with its formats, emulating the behaviour of [RDM PR #120](https://github.com/RealDeviceMap/RealDeviceMap/pull/120).

As of version 2.0, the calculations part has been moved to a separate project called [PogoPvpData](https://github.com/crhbetz/PogoPvpData), which is linked in as a submodule.

## Installation
This project can now be cloned directly into your MAD/plugins folder using the following command - [please also note the command for updating](#updating):

```git clone --recurse-submodules https://github.com/crhbetz/mp-poraclePvpHelper.git```

Downloading and distributing `.mp` files for an active project seems a little tedious to me, so cloning and pulling updates from GitHub will be considered the primary way of distribution for this plugin. I'll try to keep up with `.mp` [releases](https://github.com/crhbetz/mp-poraclePvpHelper/releases) though.

After installation, the usual setup procedure for MAD plugins applies. Copy the `plugin.ini.example` to `plugin.ini` and edit it to your personal preferences.

It is recommended to deactivate regular pokemon webhooks to endpoint(s) you're sending to with this plugin, because it sends all the pokemon
data the usual webhook worker would send, enhanced with the additional pvp data. Sending the same data through two different webhook
workers may cause unintended behaviour. You can disable regular pokemon data either by disabling pokemon webhooks
altogether, or by omitting pokemon from the list of enabled webhook types for a specific URL (example: `[raid gym weather pokestop quest]http://localhost:4201`)

Finally, restart your MAD instance.

## Updating

Updating your installation including the submodule through git will require the following command:

```git pull --recurse-submodules```

`.mp` file installs are updated by uploading a newer `.mp` file.

## Re-calculation of data
The plugin saves its `PokemonData` object to a file called `.data.pickle` within the plugin directory to aviod having to repeat the rather heavy calculations for every run of your MAD instance.
To apply certain settings or load new Pokemon / Stats / Forms, a re-calculation of the previously mentioned data will be necessary. Settings that require a recalc
will be commented accordingly in the `plugin.ini.example` file.
To achieve a recalc, delete the `.data.pickle` file and restart your MAD instance. Recalculation will be done according to your `precalc` setting.

## Multi-instance setup
This plugin is able to run across multiple MAD instances from the same MAD directory. Settings can be made instance-specific by naming a settings category
like the `status-name` of your instances. An example can be seen as a comment in the `plugin.ini.example` file.

The `.data.pickle` file can be shared across those instances, so only one initial calculation is required.

# A little disclaimer
I don't think it's the scanners job to provide this data. I think these are things that should happen in the front-end, like in
[PokeAlarm](https://github.com/pokealarm/pokealarm). However, I only speak python, so I'm unable to make a "correct" PR for PoracleJS. So instead
of complaining, I put my "beliefs" aside, accepted the status quo and created this MAD plugin which is basically a port and extension of the pvp work
I made for PokeAlarm.
