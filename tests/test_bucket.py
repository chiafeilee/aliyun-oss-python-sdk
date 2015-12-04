# -*- coding: utf-8 -*-

import unittest
import datetime
import oss2

from common import *


class TestBucket(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TestBucket, self).__init__(*args, **kwargs)
        self.bucket = None

    def setUp(self):
        self.bucket = oss2.Bucket(oss2.Auth(OSS_ID, OSS_SECRET), OSS_ENDPOINT, OSS_BUCKET)

    def test_bucket(self):
        auth = oss2.Auth(OSS_ID, OSS_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, random_string(63).lower())

        bucket.create_bucket('private')

        service = oss2.Service(auth, OSS_ENDPOINT)
        result = service.list_buckets()
        next(b for b in result.buckets if b.name == bucket.bucket_name)

        bucket.delete_bucket()

    def test_acl(self):
        auth = oss2.Auth(OSS_ID, OSS_SECRET)
        bucket = oss2.Bucket(auth, OSS_ENDPOINT, random_string(63).lower())

        bucket.create_bucket('public-read')
        result = bucket.get_bucket_acl()
        self.assertEqual(result.acl, 'public-read')

        bucket.put_bucket_acl('private')
        result = bucket.get_bucket_acl()
        self.assertEqual(result.acl, 'private')

        bucket.delete_bucket()

    def test_logging(self):
        other_bucket = oss2.Bucket(self.bucket.auth, OSS_ENDPOINT, random_string(63).lower())
        other_bucket.create_bucket('private')

        other_bucket.put_bucket_logging(oss2.models.BucketLogging(self.bucket.bucket_name, 'logging/'))

        result = other_bucket.get_bucket_logging()
        self.assertEqual(result.target_bucket, self.bucket.bucket_name)
        self.assertEqual(result.target_prefix, 'logging/')

        other_bucket.delete_bucket_logging()
        other_bucket.delete_bucket_logging()

        result = other_bucket.get_bucket_logging()
        self.assertEqual(result.target_bucket, '')
        self.assertEqual(result.target_prefix, '')

        other_bucket.delete_bucket()

    def test_website(self):
        key = random_string(12) + '/'
        content = random_bytes(32)

        self.bucket.put_object('index.html', content)

        # 设置index页面和error页面
        self.bucket.put_bucket_website(oss2.models.BucketWebsite('index.html', 'error.html'))

        # 验证index页面和error页面
        website = self.bucket.get_bucket_website()
        self.assertEqual(website.index_file, 'index.html')
        self.assertEqual(website.error_file, 'error.html')

        # 验证读取目录会重定向到index页面
        result = self.bucket.get_object(key)
        self.assertEqual(result.read(), content)

        self.bucket.delete_object('index.html')

        # 关闭静态网站托管模式
        self.bucket.delete_bucket_website()
        self.bucket.delete_bucket_website()

        # 再次关闭报错
        self.assertRaises(oss2.exceptions.NoSuchWebsite, self.bucket.get_bucket_website)

    def test_lifecycle_days(self):
        from oss2.models import LifecycleExpiration, LifecycleRule, BucketLifecycle

        rule = LifecycleRule(random_string(10), '',
                             status=LifecycleRule.DISABLED,
                             expiration=LifecycleExpiration(days=356))
        lifecycle = BucketLifecycle([rule])

        self.bucket.put_bucket_lifecycle(lifecycle)
        rule_got = self.bucket.get_bucket_lifecycle().rules[0]

        self.assertEqual(rule.id, rule_got.id)
        self.assertEqual(rule.prefix, rule_got.prefix)
        self.assertEqual(rule.status, rule_got.status)

        self.assertEqual(rule_got.expiration.days, 356)
        self.assertEqual(rule_got.expiration.date, None)

        self.bucket.delete_bucket_lifecycle()
        self.bucket.delete_bucket_lifecycle()

        self.assertRaises(oss2.exceptions.NoSuchLifecycle, self.bucket.get_bucket_lifecycle)

    def test_lifecycle_date(self):
        from oss2.models import LifecycleExpiration, LifecycleRule, BucketLifecycle

        rule = LifecycleRule(random_string(10), '',
                             status=LifecycleRule.DISABLED,
                             expiration=LifecycleExpiration(date=datetime.date(2100, 12, 25)))
        lifecycle = BucketLifecycle([rule])

        self.bucket.put_bucket_lifecycle(lifecycle)
        rule_got = self.bucket.get_bucket_lifecycle().rules[0]

        self.assertEqual(rule_got.expiration.days, None)
        self.assertEqual(rule_got.expiration.date, datetime.date(2100, 12, 25))

        self.bucket.delete_bucket_lifecycle()

    def test_cors(self):
        rule = oss2.models.CorsRule(allowed_origins=['*'],
                                   allowed_methods=['HEAD', 'GET'],
                                   allowed_headers=['*'],
                                   max_age_seconds=1000)
        cors = oss2.models.BucketCors([rule])

        self.bucket.put_bucket_cors(cors)

        cors_got = self.bucket.get_bucket_cors()
        rule_got = cors_got.rules[0]

        self.assertEqual(rule.allowed_origins, rule_got.allowed_origins)
        self.assertEqual(rule.allowed_methods, rule_got.allowed_methods)
        self.assertEqual(rule.allowed_headers, rule_got.allowed_headers)
        self.assertEqual(rule.max_age_seconds, rule_got.max_age_seconds)

        self.bucket.delete_bucket_cors()
        self.bucket.delete_bucket_cors()

        self.assertRaises(oss2.exceptions.NoSuchCors, self.bucket.get_bucket_cors)

    def test_referer(self):
        referers = ['http://hello.com', 'mibrowser:home']
        config = oss2.models.BucketReferer(True, referers)

        self.bucket.put_bucket_referer(config)
        result = self.bucket.get_bucket_referer()

        self.assertTrue(result.allow_empty_referer)
        self.assertEqual(sorted(referers), sorted(result.referers))

    def test_location(self):
        result = self.bucket.get_bucket_location()
        self.assertTrue(result.location)

    def test_xml_input_output(self):
        xml_input = '''<?xml version="1.0" encoding="UTF-8"?>
                       <RefererConfiguration>
                         <AllowEmptyReferer>true</AllowEmptyReferer>
                         <RefererList>
                            <Referer>阿里云</Referer>
                         </RefererList>
                       </RefererConfiguration>'''
        self.bucket.put_bucket_referer(xml_input)

        resp = self.bucket._get_bucket_config(oss2.Bucket.REFERER)
        result = oss2.models.GetBucketRefererResult(resp)
        oss2.xml_utils.parse_get_bucket_referer(result, resp.read())

        self.assertEqual(result.allow_empty_referer, True)
        self.assertEqual(result.referers[0], '阿里云')

    def test_bucket_exists(self):
        self.assertTrue(self.bucket.bucket_exists())

        utopia = oss2.Bucket(oss2.Auth(OSS_ID, OSS_SECRET), OSS_ENDPOINT, 'utopia-1a2b3c-zxcv-qwer')
        self.assertTrue(not utopia.bucket_exists())


if __name__ == '__main__':
    unittest.main()