from django.db import models
import uuid
import os
from random import randint, sample
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.core.signing import TimestampSigner
from django.utils.functional import cached_property
from .managers import AdvertisementManager


class Provider(models.Model):
    name = models.CharField(max_length=255)
    user = models.OneToOneField(User, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return self.name

    def active_ads(self):
        return self.advertisement_set.filter(status=Advertisement.ACTIVE).count()

    def active_ads_list(self):
        return self.advertisement_set.filter(status=Advertisement.ACTIVE)

    def inactive_ads(self):
        return self.advertisement_set.filter(status=Advertisement.INACTIVE).count()

    def total_clicks(self):
        click_count = 0
        for advert in self.advertisement_set.filter(status=Advertisement.ACTIVE):
            click_count += advert.click_set.count()
        return click_count

    def get_absolute_url(self):
        return reverse('advertisements.views.view_provider_statistics', args=[self.pk])


def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = "%s.%s" % (uuid.uuid4(), ext)
    return os.path.join('resources', filename)


class AdvertisementPanel(models.Model):
    name = models.CharField(max_length=255)
    height = models.PositiveIntegerField()
    width = models.PositiveIntegerField()

    cols = models.PositiveIntegerField(default=1)
    rows = models.PositiveIntegerField(default=1)

    @cached_property
    def ad_display_num(self):
        return self.cols * self.rows

    @cached_property
    def total_width(self):
        total_margin = 5
        return (self.cols * (self.width + total_margin)) + total_margin

    @cached_property
    def total_height(self):
        total_margin = 5
        return (self.rows * (self.height + total_margin)) + total_margin

    def get_adverts(self):
        viable_adverts = self.advertisement_set.filter(status=Advertisement.ACTIVE)

        total_ads = viable_adverts.count()

        if total_ads == 0:
            return []

        if total_ads < self.ad_display_num:
            # There are not enough ads, so just return what we have
            return list(viable_adverts)

        random_positions = sample(range(total_ads), self.ad_display_num)
        adverts = []

        for position in random_positions:
            adverts.append(viable_adverts.all()[position])

        return adverts

    def get_absolute_url(self):
        return reverse('advert:panel', args=[self.pk])

    def get_iframe_url(self):
        return '<iframe width="{0}" height="{1}" frameborder="0" scrolling="no" src="[INSERT_BASE_URL_HERE]{2}"></iframe>'.format(
            self.total_width,
            self.total_height,
            self.get_absolute_url(),
        )

    def __unicode__(self):
        return "{} ({}x{})".format(self.name, self.width, self.height)


class Advertisement(models.Model):

    ACTIVE = 'a'
    INACTIVE = 'i'
    PENDING = 'p'

    STATUS_CHOICES = (
        (ACTIVE, 'Active'),
        (INACTIVE, 'Inactive'),
        (PENDING, 'Pending'),
    )

    panel = models.ForeignKey(AdvertisementPanel)
    provider = models.ForeignKey(Provider)
    url = models.URLField(max_length=255)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=ACTIVE)

    image_height = models.IntegerField(max_length=64, editable=False)
    image_width = models.IntegerField(max_length=64, editable=False)

    image = models.ImageField(
        max_length=255,
        upload_to=get_file_path,
        height_field='image_height',
        width_field='image_width'
    )

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    objects = AdvertisementManager()

    def __unicode__(self):
        return "{0} - {1}".format(self.provider.name, self.panel)

    def clicked(self):
        click = Click(
            ad=self,
        )
        click.save()

        return click

    def click_history(self, history_days=10):
        today = timezone.now().date()
        click_data = []
        for days_back in reversed(xrange(history_days)):
            date = today - timedelta(days=days_back)
            clicks = self.click_set.filter(
                date__year=date.year,
                date__month=date.month,
                date__day=date.day,
            ).count()
            click_data.append({
                "date": date,
                "clicks": clicks
            })
        return click_data

    def get_absolute_url(self):
        return reverse('advertisements.views.view_advert_statistics', args=[self.pk])

    def get_signed_link(self):
        signer = TimestampSigner()
        advert_signed = signer.sign(self.pk)

        return reverse('advert:go', args=[advert_signed])

    def total_clicks(self):
        return self.click_set.count()


class Click(models.Model):
    ad = models.ForeignKey(Advertisement)
    date = models.DateTimeField(auto_now_add=True)

