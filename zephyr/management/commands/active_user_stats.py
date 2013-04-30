from __future__ import absolute_import

from django.core.management.base import BaseCommand
from django.conf import settings

from zephyr.models import UserProfile, UserPresence
from zephyr.lib.utils import statsd, statsd_key

from datetime import datetime, timedelta
from collections import defaultdict
import os, time

class Command(BaseCommand):
    help = """Sends active user statistics to statsd.

    Run as a cron job that runs every 10 minutes."""

    def handle(self, *args, **options):
        # Get list of all active users in the last 1 week
        cutoff = datetime.now() - timedelta(minutes=30, hours=168)

        users = UserPresence.objects.select_related().filter(timestamp__gt=cutoff)

        # Calculate 2hrs, 12hrs, 1day, 2 business days (TODO business days), 1 week bucket of stats
        hour_buckets = [2, 12, 24, 48, 168]
        user_info = defaultdict(dict)

        for last_presence in users:
            if last_presence.status == UserPresence.IDLE:
                known_active = last_presence.timestamp - timedelta(minutes=30)
            else:
                known_active = last_presence.timestamp

            for bucket in hour_buckets:
                if not bucket in user_info[last_presence.user_profile.realm.domain]:
                    user_info[last_presence.user_profile.realm.domain][bucket] = []
                if datetime.now(known_active.tzinfo) - known_active < timedelta(hours=bucket):
                    user_info[last_presence.user_profile.realm.domain][bucket].append(last_presence.user_profile.email)

        for realm, buckets in user_info.items():
            print("Realm %s" % realm)
            for hr, users in sorted(buckets.items()):
                print("\tUsers for %s: %s" % (hr, len(users)))
                statsd.gauge("users.active.%s.%shr" %  (statsd_key(realm, True), hr), len(users))

