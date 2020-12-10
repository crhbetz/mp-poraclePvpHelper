import mapadroid.utils.pluginBase
from flask import render_template, Blueprint
from mapadroid.madmin.functions import auth_required
import os
import time
import json
import sys
from threading import Thread
import itertools
import pickle
from math import sqrt, floor
from enum import Enum
import requests
import configparser
from mapadroid.utils.logging import get_logger, LoggerEnums


def parseEnumProto(url, name):
    r = requests.get(url)
    enumDict = {}
    for line in r.iter_lines(decode_unicode=True):
        if not line.startswith("syntax") and not line.startswith("package") and "=" in line:
            enumDict[line.split("=")[0].strip()] = line.split("=")[1].replace(";", "").strip()
    enumDict = addEnumInfo(name, enumDict)
    return Enum(name, enumDict)


def addEnumInfo(name, enumDict):
    additionalInfo = configparser.ConfigParser()
    additionalInfo.read(os.path.dirname(os.path.abspath(__file__)) + "/additional-enum-info.ini")
    if name in additionalInfo:
        for elem in additionalInfo[name]:
            enumDict[elem.upper()] = additionalInfo[name][elem]
    return enumDict


PokemonId = parseEnumProto("https://raw.githubusercontent.com/Furtif/POGOProtos/master/src/"
                           "POGOProtos/Enums/PokemonId.proto", "PokemonId")
Form = parseEnumProto("https://raw.githubusercontent.com/Furtif/POGOProtos/master/src/"
                      "POGOProtos/Enums/Form.proto", "Form")


class PvpBase():
    def __init__(self):
        with open("{}/cp_multipliers.json".format(os.path.dirname(os.path.abspath(__file__))), "r") as f:
            self.cp_multipliers = json.load(f)

    def __getstate__(self):
        d = self.__dict__.copy()
        if 'logger' in d:
            d['logger'] = "logger"
        return d

    def __setstate__(self, d):
        if 'logger' in d:
            d['logger'] = get_logger(LoggerEnums.plugin)
        self.__dict__.update(d)
        self.logger.debug4("{} object loaded from pickle file".format(type(self).__name__))


class Pokemon(PvpBase):
    def __init__(self, num: int, form: int, atk: int, de: int, sta: int,
            evolutions: list, ranklength: int, maxlevel: int):
        super(Pokemon, self).__init__()
        self.num = num
        self.form = form
        self.atk = atk
        self.de = de
        self.sta = sta
        self.evolutions = evolutions
        self.ranklength = ranklength
        self.maxlevel = maxlevel
        self.logger = get_logger(LoggerEnums.plugin)

        self.products = {}
        self.greatPerfect, self.greatLowest = self._spreads(1500)
        self.ultraPerfect, self.ultraLowest = self._spreads(2500)
        self.logger.debug("Pokemon {}, form {} initialized".format(self.num, self.form))

    def num(self):
        return int(self.num)

    def form(self):
        return int(self.form)

    def ident(self):
        return str("{}-{}".format(self.num, self.form))

    def __str__(self):
        return "{{'num': {}, 'form': {}, 'atk': {}, 'de': {}, 'sta': {}, 'evolutions': {}}}".format(
            self.num, self.form, self.atk, self.de, self.sta, self.evolutions)

    def calculate_cp(self, atk, de, sta, lvl):
        lvl = str(lvl).replace(".0", "")
        cp = ((self.atk + atk) * sqrt(self.de + de) * sqrt(self.sta + sta) * (self.cp_multipliers[str(lvl)]**2) / 10)
        return int(cp)

    def max_cp(self):
        return self.calculate_cp(15, 15, 15, self.maxlevel)

    def getEvolution(self):
        if self.evolutions:
            self.logger.debug("getEvolution returning {}".format(self.evolutions))
            return self.evolutions
        else:
            return False

    def pokemon_rating(self, limit, atk, de, sta, lvl):
        highest_rating = 0
        highest_cp = 0
        highest_level = 0
        highest_product = 0
        rank = 4096
        min_level = max(self.min_level(limit), lvl)
        max_level = self.max_level(limit)

        if min_level > max_level:
            return 0, 0, 0, 4096

        for level in range(int(min_level * 2), int((max_level + 0.5) * 2)):
            level = str(level / float(2)).replace(".0", "")
            cp = self.calculate_cp(atk, de, sta, level)
            if not cp > limit:
                attack = (self.atk + atk) * self.cp_multipliers[str(level)]
                defense = (self.de + de) * self.cp_multipliers[str(level)]
                stamina = int(((self.sta + sta) * (self.cp_multipliers[str(level)])))
                product = attack * defense * stamina
                if product > highest_rating:
                    highest_rating = product
                    highest_cp = cp
                    highest_level = level
                    highest_product = product
        try:
            rank = self.products[limit].index(highest_product) + 1
        except Exception:
            rank = 4096
        return highest_rating, highest_cp, highest_level, rank

    def max_level(self, limit):
        if not self.max_cp() > limit:
            return float(self.maxlevel)
        for x in range(self.maxlevel * 2, 2, -1):
            x = (x * 0.5)
            if self.calculate_cp(0, 0, 0, x) <= limit:
                return min(x + 1, self.maxlevel)

    def min_level(self, limit):
        if not self.max_cp() > limit:
            return float(self.maxlevel)
        for x in range(self.maxlevel * 2, 2, -1):
            x = (x * 0.5)
            if self.calculate_cp(15, 15, 15, x) <= limit:
                return max(x - 1, 1)

    def _spreads(self, limit):
        smallest = {"product": 999999999}
        highest = {"product": 0}
        if limit not in self.products:
            self.products[limit] = []

        min_level = self.min_level(limit)
        max_level = self.max_level(limit)

        for level in range(int(min_level * 2), int((max_level + 0.5) * 2)):
            level = str(level / 2).replace('.0', '')

            for stat_product in itertools.product(range(16), range(16), range(16)):
                cp = self.calculate_cp(stat_product[0], stat_product[1], stat_product[2], level)
                if cp > limit:
                    continue

                attack = ((self.atk + stat_product[0]) * (
                    self.cp_multipliers[str(level)]))
                defense = ((self.de + stat_product[1]) * (
                    self.cp_multipliers[str(level)]))
                stamina = floor(((self.sta + stat_product[2]) * (
                    self.cp_multipliers[str(level)])))
                product = (attack * defense * stamina)
                self.products[limit].append(product)
                if product > highest["product"]:
                    highest.update({
                        'product': product,
                        'attack': attack,
                        'defense': defense,
                        'stamina': stamina,
                        'atk': stat_product[0],
                        'de': stat_product[1],
                        'sta': stat_product[2],
                        'cp': cp,
                        'level': level
                    })
                if product < smallest["product"]:
                    smallest.update({
                        'product': product,
                        'attack': attack,
                        'defense': defense,
                        'stamina': stamina,
                        'atk': stat_product[0],
                        'de': stat_product[1],
                        'sta': stat_product[2],
                        'cp': cp,
                        'level': level
                    })
        self.products[limit].sort(reverse=True)
        length = self.ranklength + 1
        del self.products[limit][length:]
        return highest, smallest


class PokemonData(PvpBase):
    def __init__(self, ranklength, maxlevel, precalc=False):
        super(PokemonData, self).__init__()
        self.logger = get_logger(LoggerEnums.plugin)
        self.templates = None
        self.gmtime = None
        self._changed = False
        self.ranklength = ranklength
        self.maxlevel = maxlevel
        self.data = {}
        self.PokemonId = PokemonId
        self.Form = Form
        if precalc:
            self.logger.warning("initializing PokemonData, this will take a while ...")
            self.processGameMaster()

    def getGameMaster(self):
        self.logger.debug2("getGameMaster called")
        if not self.templates or not self.gmtime or self.gmtime < int(time.time()) - 3600:
            self.logger.debug("download game master")
            gmfile = requests.get("https://raw.githubusercontent.com/PokeMiners/game_masters/master/latest/latest.json")
            self.templates = gmfile.json()
            self.gmtime = int(time.time())


    def processGameMaster(self, recalcIds: list = []):
        self.getGameMaster()
        if recalcIds:
            self.logger.debug(f"trying to calculate {recalcIds}")

        i = 0
        for template in self.templates:
            if (template["templateId"] and template["templateId"].startswith("V")
                    and not template["templateId"].startswith("VS") and "POKEMON" in template["templateId"]
                    and "HOME_FORM_REVERSION" not in template["templateId"]
                    and "HOME_REVERSION" not in template["templateId"]
                    and "pokemonSettings" in template["data"] and "stats" in template["data"]["pokemonSettings"]
                    and "baseAttack" in template["data"]["pokemonSettings"]["stats"]):
                if i > 0 and i % 50 == 0 and not recalcIds:
                    self.logger.success("processed {} pokemon templates ...".format(i))
                i += 1
                try:
                    moninfo = template["data"]["pokemonSettings"]
                    stats = moninfo["stats"]
                    evolution = []
                    try:
                        for evo in moninfo["evolutionBranch"]:
                            evoId = self.PokemonId[evo["evolution"]].value
                            try:
                                formId = self.Form[evo["form"]].value
                            except Exception:
                                formId = self.Form["{}_NORMAL".format(evo["evolution"])].value
                            evolution.append("{}-{}".format(evoId, formId))
                    except KeyError:
                        evolution = []

                    form = 0
                    if "form" in moninfo:
                        try:
                            form = self.Form[moninfo["form"]].value
                        except KeyError:
                            pass
                    if form == 0:
                        candidates = [moninfo["pokemonId"].replace("_FEMALE", "").replace("_MALE", "") + "_NORMAL",
                                      moninfo["pokemonId"].replace("_FEMALE", "").replace("_MALE", "")]
                        for name in candidates:
                            try:
                                form = self.Form["{}".format(name)].value
                                break
                            except KeyError:
                                form = 0

                    if form == 0 and not recalcIds:
                        self.logger.warning("Unable to determine form ID for template {} - fall back to 0",
                                            template["templateId"])

                    if not recalcIds or (recalcIds and str(self.PokemonId[moninfo["pokemonId"]].value) in recalcIds):
                        self.logger.debug(f"calculating {self.PokemonId[moninfo['pokemonId']].value}-{form}")
                        mon = Pokemon(self.PokemonId[moninfo["pokemonId"]].value,
                                      form,
                                      stats["baseAttack"],
                                      stats["baseDefense"],
                                      stats["baseStamina"],
                                      evolution,
                                      self.ranklength,
                                      self.maxlevel)
                        self.add(mon)
                        self.logger.debug("processed template {}".format(template["templateId"]))
                    else:
                        self.logger.debug("skipped template {}".format(template["templateId"]))
                except Exception as e:
                    self.logger.warning("Exception processing template {}: {} (this is probably ok)".format(
                        template["templateId"], e))
                    continue
            else:
                continue

    def add(self, pokemon: Pokemon):
        self._changed = True
        self.logger.debug(f"added {pokemon.ident()}")
        self.data[pokemon.ident()] = pokemon

    def is_changed(self):
        return self._changed

    def saved(self):
        self._changed = False

    def __str__(self):
        return str(self.data)

    def getUniqueIdentifier(self, mon, form):
        return "{}-{}".format(mon, form)

    def getPokemonObject(self, mon, form):
        identifier = self.getUniqueIdentifier(mon, form)
        if identifier in self.data:
            return self.data[identifier]
        else:
            self.logger.warning("mon {} form {} not in data. Trying to calculate it ...", mon, form)
            self.processGameMaster(recalcIds=[str(mon),])
            time.sleep(1)
            if identifier in self.data:
                self.logger.success(f"Successfully calculated and added mon {mon} to data")
                return self.data[identifier]
            else:
                self.logger.error("Unable to find or calculate mon {} form {}. Please try a full recalc or notify the "
                                  "dev :)", mon, form)
            return False

    def getAllEvolutions(self, mon, form):
        allEvolutions = []
        try:
            nextEvolution = self.getPokemonObject(mon, form).getEvolution()
        except Exception:
            nextEvolution = False
        while nextEvolution:
            for evolution in nextEvolution:
                allEvolutions.append(evolution)
                furtherEvolutions = self.getAllEvolutions(evolution.split("-")[0], evolution.split("-")[1])
                allEvolutions = allEvolutions + furtherEvolutions
            try:
                nextEvolution = self.data[nextEvolution].getEvolution()
            except Exception:
                nextEvolution = False
        self.logger.debug("found evolutions: {}".format(allEvolutions))
        return allEvolutions

    def getBaseStats(self, mon, form):
        mon = self.getPokemonObject(mon, form)
        stats = {}
        stats["attack"] = mon.atk
        stats["defense"] = mon.de
        stats["stamina"] = mon.sta
        return stats

    def get_pvp_info(self, atk, de, sta, lvl, monster=0, form=0, identifier=None):
        if identifier:
            monster = identifier.split("-")[0]
            form = identifier.split("-")[1]
        elif monster != 0 and form != 0:
            pass
        else:
            return False, False, False, False, False, False, False, False, False, False

        mondata = self.getPokemonObject(monster, form)

        if not mondata:
            return 0, 0, 0, 0, 4096, 0, 0, 0, 0, 4096

        lvl = float(lvl)
        stats_great_product = mondata.greatPerfect["product"]
        stats_ultra_product = mondata.ultraPerfect["product"]

        great_product, great_cp, great_level, great_rank = mondata.pokemon_rating(1500, atk, de, sta, lvl)
        great_rating = 100 * (great_product / stats_great_product)
        ultra_product, ultra_cp, ultra_level, ultra_rank = mondata.pokemon_rating(2500, atk, de, sta, lvl)
        ultra_rating = 100 * (ultra_product / stats_ultra_product)
        great_id = monster
        ultra_id = monster

        return (great_rating, great_id, great_cp, great_level, great_rank,
                ultra_rating, ultra_id, ultra_cp, ultra_level, ultra_rank)

    def getPoraclePvpInfo(self, mon, form, atk, de, sta, lvl):
        if form == 0:
            try:
                form = self.Form["{}_NORMAL".format(self.PokemonId(str(mon)).name)].value
            except KeyError:
                form = 0
        greatPayload = []
        ultraPayload = []
        evolutions = [self.getUniqueIdentifier(mon, form), ] + self.getAllEvolutions(mon, form)

        for evolution in evolutions:
            grating, gid, gcp, glvl, grank, urating, uid, ucp, ulvl, urank = self.get_pvp_info(atk, de, sta, lvl,
                                                                                               identifier=evolution)
            if grank < 4096:
                greatPayload.append(
                    {
                        'rank': grank,
                        'percentage': round(grating, 3),
                        'pokemon': evolution.split("-")[0],
                        'form': evolution.split("-")[1],
                        'level': glvl,
                        'cp': gcp
                    })
            if urank < 4096:
                ultraPayload.append(
                    {
                        'rank': urank,
                        'percentage': round(urating, 3),
                        'pokemon': evolution.split("-")[0],
                        'form': evolution.split("-")[1],
                        'level': ulvl,
                        'cp': ucp
                    })
        return greatPayload, ultraPayload


class poraclePvpHelper(mapadroid.utils.pluginBase.Plugin):
    """poraclePvpHelper plugin
    """
    def __init__(self, mad):
        super().__init__(mad)

        self._rootdir = os.path.dirname(os.path.abspath(__file__))
        sys.path.append(self._rootdir)

        self._mad = mad
        self.db = self._mad["db_wrapper"]
        self.logger = get_logger(LoggerEnums.plugin)
        self.wh = self._mad["webhook_worker"]

        self.statusname = self._mad["args"].status_name
        self._pluginconfig.read(self._rootdir + "/plugin.ini")
        self._versionconfig.read(self._rootdir + "/version.mpl")
        self.author = self._versionconfig.get("plugin", "author", fallback="unknown")
        self.url = self._versionconfig.get("plugin", "url", fallback="https://www.maddev.eu")
        self.description = self._versionconfig.get("plugin", "description", fallback="unknown")
        self.version = self._versionconfig.get("plugin", "version", fallback="unknown")
        self.pluginname = self._versionconfig.get("plugin", "pluginname", fallback="https://www.maddev.eu")
        self.staticpath = self._rootdir + "/static/"
        self.templatepath = self._rootdir + "/template/"

        # plugin specific
        if self.statusname in self._pluginconfig:
            self.logger.success("Applying specific config for status-name {}!", self.statusname)
            settings = self.statusname
        else:
            self.logger.info("Using generic settings on instance with status-name {}", self.statusname)
            settings = "settings"
        self.target = self._pluginconfig.get(settings, "target", fallback=None)
        self.interval = self._pluginconfig.getint(settings, "interval", fallback=30)
        self.ranklength = self._pluginconfig.getint(settings, "ranklength", fallback=100)
        self.maxlevel = self._pluginconfig.getint(settings, "maxlevel", fallback=50)
        self.precalc = self._pluginconfig.getboolean(settings, "precalc", fallback=False)
        self.saveData = self._pluginconfig.getboolean(settings, "savedata", fallback=True)

        self._routes = [
            ("/poraclePvpHelper_manual", self.manual),
        ]

        self._hotlink = [
            ("poraclePvpHelper Manual", "poraclePvpHelper_manual", "poraclePvpHelper Manual"),
        ]

        if self._pluginconfig.getboolean("plugin", "active", fallback=False):
            self._plugin = Blueprint(str(self.pluginname), __name__, static_folder=self.staticpath,
                                     template_folder=self.templatepath)

            for route, view_func in self._routes:
                self._plugin.add_url_rule(route, route.replace("/", ""), view_func=view_func)

            for name, link, description in self._hotlink:
                self._mad['madmin'].add_plugin_hotlink(name, self._plugin.name + "." + link.replace("/", ""),
                                                       self.pluginname, self.description, self.author, self.url,
                                                       description, self.version)

    def perform_operation(self):
        # do not change this part ▽▽▽▽▽▽▽▽▽▽▽▽▽▽▽
        if not self._pluginconfig.getboolean("plugin", "active", fallback=False):
            return False
        self._mad['madmin'].register_plugin(self._plugin)
        # do not change this part △△△△△△△△△△△△△△△

        if not self._mad["args"].webhook:
            self.logger.error("Webhook worker is required but not enabled. Please set 'webhook' in your config "
                              "and restart. Stopping the plugin.")
            return False

        # load your stuff now
        self.logger.success("poraclePvpHelper Plugin starting operations ...")
        poraclePvpHelper = Thread(name="poraclePvpHelper", target=self.poraclePvpHelper,)
        poraclePvpHelper.daemon = True
        poraclePvpHelper.start()

        updateChecker = Thread(name="poraclePvpHelperUpdates", target=self.update_checker,)
        updateChecker.daemon = True
        updateChecker.start()

        return True

    def _pickle_data(self, data):
        if self.saveData:
            try:
                with open("{}/.data.pickle".format(os.path.dirname(os.path.abspath(__file__))), "wb") as datafile:
                    pickle.dump(data, datafile, -1)
                    self.logger.success("Saved data to pickle file")
                    return True
            except Exception as e:
                self.logger.warning("Failed saving to pickle file: {}".format(e))
                return False
        else:
            return False

    def _is_update_available(self):
        update_available = None
        try:
            r = requests.get("https://raw.githubusercontent.com/crhbetz/mp-poraclePvpHelper/master/version.mpl")
            self.github_mpl = configparser.ConfigParser()
            self.github_mpl.read_string(r.text)
            self.available_version = self.github_mpl.get("plugin", "version", fallback=self.version)
        except Exception:
            return None

        try:
            from pkg_resources import parse_version
            update_available = parse_version(self.version) < parse_version(self.available_version)
        except Exception:
            pass

        if update_available is None:
            try:
                from distutils.version import LooseVersion
                update_available = LooseVersion(self.version) < LooseVersion(self.available_version)
            except Exception:
                pass

        if update_available is None:
            try:
                from packaging import version
                update_available = version.parse(self.version) < version.parse(self.available_version)
            except Exception:
                pass

        return update_available

    def update_checker(self):
        while True:
            self.logger.debug("poraclePvpHelper checking for updates ...")
            result = self._is_update_available()
            if result:
                self.logger.warning("An update of poraclePvpHelper from version {} to version {} is available!",
                                    self.version, self.available_version)
            elif result is False:
                self.logger.success("poraclePvpHelper is up-to-date! ({} = {})", self.version, self.available_version)
            else:
                self.logger.warning("Failed checking for updates!")
            time.sleep(3600)

    # copied from mapadroid/webhook/webhookworker.py
    def _payload_chunk(self, payload, size):
        if size == 0:
            return [payload]

        return [payload[x: x + size] for x in range(0, len(payload), size)]

    # copied from mapadroid/webhook/webhookworker.py + some variables adjusted
    def _send_webhook(self, payloads):
        if len(payloads) == 0:
            self.logger.debug2("Payload empty. Skip sending to webhook.")
            return

        # get list of urls
        webhooks = self.target.replace(" ", "").split(",")

        webhook_count = len(webhooks)
        current_wh_num = 1

        for webhook in webhooks:
            payload_to_send = []
            sub_types = "all"
            url = webhook.strip()

            if url.startswith("["):
                end_index = webhook.rindex("]")
                end_index += 1
                sub_types = webhook[:end_index]
                url = url[end_index:]

                for payload in payloads:
                    if payload["type"] in sub_types:
                        payload_to_send.append(payload)
            else:
                payload_to_send = payloads

            if len(payload_to_send) == 0:
                self.logger.debug2("Payload empty. Skip sending to: {} (Filter: {})", url, sub_types)
                continue
            else:
                self.logger.debug2("Sending to webhook url: {} (Filter: {})", url, sub_types)

            payload_list = self._payload_chunk(payloads, self._mad["args"].webhook_max_payload_size)

            current_pl_num = 1
            for payload_chunk in payload_list:
                self.logger.debug4("Python data for payload: {}", payload_chunk)
                self.logger.debug4("Payload: {}", json.dumps(payload_chunk))

                try:
                    response = requests.post(
                        url,
                        data=json.dumps(payload_chunk),
                        headers={"Content-Type": "application/json"},
                        timeout=5,
                    )

                    if response.status_code != 200:
                        self.logger.warning("Got status code other than 200 OK from webhook destination: {}",
                                            response.status_code)
                    else:
                        if webhook_count > 1:
                            whcount_text = " [wh {}/{}]".format(current_wh_num, webhook_count)
                        else:
                            whcount_text = ""

                        if len(payload_list) > 1:
                            whchunk_text = " [pl {}/{}]".format(current_pl_num, len(payload_list))
                        else:
                            whchunk_text = ""

                        self.logger.success("Successfully sent poraclePvpHelper data to webhook{}{}. Mons sent: {}",
                                            whchunk_text, whcount_text, len(payload_chunk))
                except Exception as e:
                    self.logger.warning("Exception occured while sending webhook: {}", e)

                current_pl_num += 1
            current_wh_num += 1

    def poraclePvpHelper(self):
        self.__last_check = int(time.time())
        if not self.target:
            self.logger.error("no webhook (target) defined in settings - what am I doing here? ;)")
            return False

        if os.path.isfile("{}/data.pickle".format(self._rootdir)):
            os.rename("{}/data.pickle".format(self._rootdir), "{}/.data.pickle".format(self._rootdir))
            self.logger.success("migrated data.pickle to .data.pickle (hidden file)")

        try:
            with open("{}/.data.pickle".format(self._rootdir), "rb") as datafile:
                data = pickle.load(datafile)
        except Exception as e:
            self.logger.debug("exception trying to load pickle'd data: {}".format(e))
            self.logger.warning("Failed loading previously calculated data - start initialization")
            data = None

        if not data:
            data = PokemonData(self.ranklength, self.maxlevel, precalc=self.precalc)
            self._pickle_data(data)

        if not data:
            self.logger.error("Failed aquiring PokemonData object! Stopping the plugin.")
            return False

        self.logger.success("PokemonData object aquired")

        w = 0
        while not self.wh and w < 12:
            w += 1
            self.logger.warning("waiting for the webhook worker to be initialized ...")
            time.sleep(10)
        if w > 11:
            self.logger.error("Failed trying to access the webhook worker with webhook enabled. Please contact "
                              "the developer.")
            return False

        while True:
            try:
                starttime = int(time.time())
                monsFromDb = self.db.webhook_reader.get_mon_changed_since(self.__last_check)
                payload = self.wh._WebhookWorker__prepare_mon_data(monsFromDb)
                for mon in payload:
                    if "individual_attack" in mon["message"]:
                        content = mon["message"]
                        try:
                            form = content["form"]
                        except Exception:
                            form = 0
                        try:
                            great, ultra = data.getPoraclePvpInfo(content["pokemon_id"], form,
                                                                  content["individual_attack"],
                                                                  content["individual_defense"],
                                                                  content["individual_stamina"],
                                                                  content["pokemon_level"])
                        except Exception:
                            self.logger.warning("Failed processing mon #{}-{}. Skipping.", content["pokemon_id"], form)
                            continue
                        if len(great) > 0:
                            mon["message"]["pvp_rankings_great_league"] = great
                        if len(ultra) > 0:
                            mon["message"]["pvp_rankings_ultra_league"] = ultra
                self._send_webhook(payload)

                if self.saveData and data.is_changed():
                    self._pickle_data(data)
                    data.saved()

            except Exception:
                self.logger.opt(exception=True).error("Unhandled exception in poraclePvpHelper! Trying to continue... "
                                                      "Please notify the developer!")
            self.__last_check = starttime
            time.sleep(self.interval)

    @auth_required
    def manual(self):
        return render_template("poraclePvpHelper_manual.html",
                               header="poraclePvpHelper manual", title="poraclePvpHelper manual"
                               )
