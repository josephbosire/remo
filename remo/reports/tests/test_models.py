import datetime

from django.core import mail
from nose.tools import eq_, ok_
from test_utils import TestCase

import fudge

from remo.base.utils import go_back_n_months
from remo.events.helpers import get_event_link
from remo.events.tests import EventFactory, AttendanceFactory
from remo.profiles.tests import UserFactory
from remo.reports.models import (OVERDUE_DAY, NGReport,
                                 EVENT_ATTENDANCE_ACTIVITY)
from remo.reports.tests import (NGReportFactory, NGReportCommentFactory,
                                ReportCommentFactory, ReportFactory)


class ModelTest(TestCase):
    """Tests related to Reports Models."""

    def setUp(self):
        """Setup tests."""
        self.new_mentor = UserFactory.create(username='mentor',
                                             groups=['Mentor'])
        self.user_mentor = UserFactory.create(username='counselor',
                                              groups=['Mentor'])
        self.user = UserFactory.create(username='rep', groups=['Rep'],
                                       userprofile__mentor=self.user_mentor)
        self.month_year = datetime.date(year=2012, month=1, day=10)
        self.report = ReportFactory.create(user=self.user,
                                           month=self.month_year,
                                           mentor=self.user.userprofile.mentor)

    def test_mentor_set_for_new_report(self):
        """Test that report mentor field stays the same when user

           changes mentor.
        """
        eq_(self.report.mentor, self.user.userprofile.mentor)

        # Change user mentor and re-save the report. Report should
        # point to the first mentor.
        self.user.userprofile.mentor = self.new_mentor
        self.user.save()

        self.report.save()
        eq_(self.report.mentor, self.user_mentor)

    def test_overdue_true(self):
        """Test overdue report (first test)."""
        eq_(self.report.overdue, True)

    @fudge.patch('datetime.date.today')
    def test_overdue_true_2(self, fake_requests_obj):
        """Test overdue report (second test)."""
        today = datetime.datetime.today()

        # act like it's OVERDUE_DAY + 1
        fake_date = datetime.datetime(year=today.year, month=today.month,
                                      day=OVERDUE_DAY + 1)
        (fake_requests_obj.expects_call().returns(fake_date))

        month_year = go_back_n_months(today)
        report = ReportFactory.create(user=self.user, month=month_year)
        eq_(report.overdue, True)

    def test_overdue_false(self):
        """Test not overdue report (first test)."""
        # Change report created_on, so report is not overdue
        month_year = datetime.date(year=2020, month=1, day=10)
        report = ReportFactory.create(user=self.user, month=month_year)
        eq_(report.overdue, False)

    @fudge.patch('datetime.date.today')
    def test_overdue_false_2(self, fake_requests_obj):
        """Test not overdue report (first test)."""
        # marginal case
        today = datetime.datetime.today()

        # act like it's OVERDUE_DAY
        fake_date = datetime.datetime(year=today.year, month=today.month,
                                      day=OVERDUE_DAY)
        (fake_requests_obj.expects_call().returns(fake_date))

        month_year = go_back_n_months(today)
        report = ReportFactory.create(user=self.user, month=month_year)
        eq_(report.overdue, False)

    def test_set_month_day(self):
        """Test that reports month always points to first day of the month."""
        eq_(self.report.month.day, 1)


class MentorNotificationOnAddEditReport(TestCase):
    """Test that a Mentor receives an email when a Mentee

        adds/edits a report.
    """

    def setUp(self):
        self.date = datetime.datetime.now()
        self.mentor = UserFactory.create(username='counselor',
                                         groups=['Mentor'])
        self.user = UserFactory.create(username='rep', groups=['Rep'],
                                       userprofile__mentor=self.mentor)
        self.month_year = datetime.date(year=2012, month=1, day=10)
        self.new_report = ReportFactory.build(
            user=self.user, month=self.date,
            mentor=self.user.userprofile.mentor)
        self.mentor_profile = self.mentor.userprofile

    def test_send_email_on_add_report(self):
        """Test sending an email when a new report is added.

           Default option: True
        """
        self.new_report.save()
        eq_(len(mail.outbox), 1)

    def test_send_email_on_add_report_with_receive_mail_False(self):
        """Test sending an email when a new report is added

           and Mentor has the option in his/her settings disabled.
        """
        self.mentor_profile.receive_email_on_add_report = False
        self.mentor_profile.save()

        self.new_report.save()
        eq_(len(mail.outbox), 0)

    def test_send_email_on_edit_report_with_receive_mail_False(self):
        """Test sending an email when a report is edited.

           Default option: False
        """
        self.mentor_profile.receive_email_on_edit_report = False
        self.mentor_profile.receive_email_on_add_report = False
        self.mentor_profile.save()

        ReportFactory.create(user=self.user, mentor=self.mentor)
        eq_(len(mail.outbox), 0)

    def test_send_email_on_edit_report_with_receive_mail_True(self):
        """Test sending an email when a report is edited

           and Mentor has the option in his/her settings enabled.
        """
        self.mentor_profile.receive_email_on_edit_report = True
        self.mentor_profile.save()

        ReportFactory.create(user=self.user, mentor=self.mentor)
        eq_(len(mail.outbox), 1)


class UserNotificationOnAddComment(TestCase):
    """Test that a user receives an email when an authenticated user

    adds a comment on a report.
    """

    def setUp(self):
        self.date = datetime.datetime.now()
        self.mentor = UserFactory.create(
            username='counselor', groups=['Mentor'],
            userprofile__receive_email_on_add_report=False)
        self.user = UserFactory.create(username='rep', groups=['Rep'],
                                       userprofile__mentor=self.mentor)
        self.user_profile = self.user.userprofile
        self.report = ReportFactory.create(user=self.user,
                                           month=self.date,
                                           mentor=self.user.userprofile.mentor)
        self.new_comment = ReportCommentFactory.build(user=self.mentor,
                                                      created_on=self.date,
                                                      report=self.report)
        self.month_year = datetime.date(year=2012, month=1, day=10)

    def test_send_email_on_add_comment_with_receive_mail_True(self):
        """Test sending email when a new comment is added.

        Default option: True
        """
        self.new_comment.save()
        eq_(len(mail.outbox), 1)

    def test_send_email_on_add_comment_with_receive_mail_False(self):
        """Test sending email when a new comment is added and

        user has the option disabled in his/her settings.
        """
        self.user_profile.receive_email_on_add_comment = False
        self.user_profile.save()

        self.new_comment.save()
        eq_(len(mail.outbox), 0)


class NGReportTest(TestCase):
    def test_get_absolute_url(self):
        report = NGReportFactory.create(
            report_date=datetime.date(2012, 01, 01), id=9999)
        eq_(report.get_absolute_url(),
            ('/u/%s/r/2012/January/1/9999/'
             % report.user.userprofile.display_name))

    def test_get_absolute_edit_url(self):
        report = NGReportFactory.create(
            report_date=datetime.date(2012, 01, 01), id=9999)
        eq_(report.get_absolute_edit_url(),
            ('/u/%s/r/2012/January/1/9999/edit/'
             % report.user.userprofile.display_name))

    def test_get_absolute_delete_url(self):
        report = NGReportFactory.create(
            report_date=datetime.date(2012, 01, 01), id=9999)
        eq_(report.get_absolute_delete_url(),
            ('/u/%s/r/2012/January/1/9999/delete/'
             % report.user.userprofile.display_name))


class NGReportComment(TestCase):
    def test_get_absolute_delete_url(self):
        report = NGReportFactory.create(
            report_date=datetime.date(2012, 01, 01), id=9999)
        report_comment = NGReportCommentFactory.create(report=report,
                                                       user=report.user)
        eq_(report_comment.get_absolute_delete_url(),
            ('/u/%s/r/2012/January/1/9999/comment/%s/delete/'
             % (report.user.userprofile.display_name, report_comment.id)))


class NGReportSignalsTest(TestCase):
    def test_create_passive_event_attendance_report_owner(self):
        """Test creating a passive attendance report for event owner."""
        user = UserFactory.create(groups=['Rep', 'Mentor'],
                                  userprofile__initial_council=True)
        event = EventFactory.create(owner=user)
        report = NGReport.objects.get(event=event, user=user)

        eq_(report.mentor, user.userprofile.mentor)
        eq_(report.activity.name, EVENT_ATTENDANCE_ACTIVITY)
        eq_(report.latitude, event.lat)
        eq_(report.longitude, event.lon)
        eq_(report.location, event.venue)
        eq_(report.is_passive, True)
        eq_(report.link, get_event_link(event))
        eq_(report.activity_description, event.description)
        self.assertQuerysetEqual(report.functional_areas.all(),
                                 [e.name for e in event.categories.all()],
                                 lambda x: x.name)

    def test_create_passive_event_attendance_report(self):
        """Test creating a passive report after attending an event."""
        event = EventFactory.create()
        user = UserFactory.create(groups=['Rep', 'Mentor'],
                                  userprofile__initial_council=True)
        AttendanceFactory.create(event=event, user=user)
        report = NGReport.objects.get(event=event, user=user)

        eq_(report.mentor, user.userprofile.mentor)
        eq_(report.activity.name, EVENT_ATTENDANCE_ACTIVITY)
        eq_(report.latitude, event.lat)
        eq_(report.longitude, event.lon)
        eq_(report.location, event.venue)
        eq_(report.is_passive, True)
        eq_(report.link, get_event_link(event))
        eq_(report.activity_description, event.description)
        self.assertQuerysetEqual(report.functional_areas.all(),
                                 [e.name for e in event.categories.all()],
                                 lambda x: x.name)

    def test_delete_passive_event_attendance_report(self):
        """Test delete passive report after attendance delete."""
        event = EventFactory.create()
        user = UserFactory.create(groups=['Rep', 'Mentor'],
                                  userprofile__initial_council=True)
        attendance = AttendanceFactory.create(event=event, user=user)
        ok_(NGReport.objects.filter(event=event, user=user).exists())
        attendance.delete()
        ok_(not NGReport.objects.filter(event=event, user=user).exists())

    def test_update_report_after_event_edit(self):
        """Test update report after event edit."""
        event = EventFactory.create()
        report = NGReportFactory.create(user=event.owner, event=event,
                                        report_date=event.start)
        eq_(report.report_date, event.start)

        event.start += datetime.timedelta(days=5)
        event.end += datetime.timedelta(days=5)
        event.save()

        report = NGReport.objects.get(event=event, user=event.owner)
        eq_(report.report_date.day, event.start.day)

    def test_update_report_after_event_functional_areas_edit(self):
        """Test update report after changes in event's functional areas."""
        event = EventFactory.create()
        categories = event.categories.all()
        report = NGReportFactory.create(user=event.owner, event=event,
                                        functional_areas=categories)

        event.categories = categories[:1]
        self.assertQuerysetEqual(report.functional_areas.all(),
                                 [e.name for e in categories.all()[:1]],
                                 lambda x: x.name)
