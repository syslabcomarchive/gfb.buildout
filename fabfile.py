# Copyright (c) 2010 gocept gmbh & co. kg
# See also LICENSE.txt


from fabric.api import *
from fabric.contrib.files import *
import websites
import time

branch = 'https://code.gocept.com/svn/osha/gfb.buildout/trunk'
#deliverance_branch = 'https://code.gocept.com/svn/osha/deliverance_osha/trunk'
#awstatsreport_branch = 'https://code.gocept.com/svn/osha/awstatsreport/trunk'
PRODUCTION_HOSTS = ['oshaweb%02i.gocept.net' % x for x in range(27)]
STAGING_HOSTS = ['oshawebtest%02i.gocept.net' % x for x in range(5)]
INTEGRATION_HOSTS = ['ext%01i.syslab.com' % x for x in range(5,7)]
PYPI = 'http://services02.fe.rzob.gocept.net/pypi/setuptools'


# XXX duplicated from buildout
VARNISH_ADDRESS = dict(integration='ext6.syslab.com:8008',
                       staging='oshawebtest00.gocept.net:8008',
                       production='oshaweb00.gocept.net:8008')
#DELIVERANCE_ADDRESS = dict(integration='ext6.syslab.com:8000',
                           staging='oshawebtest00.gocept.net:8000',
                           production='oshaweb26.gocept.net:8000')
NGINX_ADDRESS = dict(integration='ext6.syslab.com:80',
                     staging='195.62.125.50:80',
                     production='195.62.125.6:80')
#MEDIA_ADDRESS = dict(integration='ext6.syslab.com:80',
                     staging='195.62.125.52:80',
                     production='195.62.125.61:80')
#BIRT_ADDRESS = dict(integration='ext6.syslab.com:82',
                    staging='195.62.125.68:80',
                    production='195.62.125.14:80')
#POSTGRES_SERVER = dict(integration='ext5.syslab.com',
                       staging='oshawebtest03.gocept.net',
                       production='oshaweb21.gocept.net')
DNS_SUFFIX = dict(integration='test.osha.syslab.com',
                  staging='test.osha.europa.eu',
                  production='')
DOMAIN_SUFFIX = dict(integration='.syslab.com',
                     staging='.gocept.net',
                     production='.gocept.net')

# Fabric commands. These commands bundle the execution of deployment for
# staging and production into separate commands with predefined host-lists.
# You can call them directly via `fab staging` or `fab production`.

@hosts(*INTEGRATION_HOSTS)
def integration():
    deploy(base_profile='integration')

@hosts(*STAGING_HOSTS)
def staging():
    deploy(base_profile='staging')

@hosts(*PRODUCTION_HOSTS)
def production():
    deploy(base_profile='production')

@hosts(*PRODUCTION_HOSTS)
def zope_ctl(cmd):
    setting = settings[env.host.replace(DOMAIN_SUFFIX['production'], '')]
    if zope not in setting['profiles']:
        return
    with cd('/home/zope/gfb'):
        gfb('bin/instance %s' % cmd)

@hosts(*STAGING_HOSTS)
def zope_ctl_staging(cmd):
    setting = settings[env.host.replace(DOMAIN_SUFFIX['staging'], '')]
    if zope not in setting['profiles']:
        return
    with cd('/home/zope/gfb'):
        gfb('bin/instance %s' % cmd)

@hosts(*INTEGRATION_HOSTS)
def zope_ctl_integration(cmd):
    setting = settings[env.host.replace(DOMAIN_SUFFIX['integration'], '')]
    if zope not in setting['profiles']:
        return
    with cd('/home/zope/gfb'):
        gfb('bin/instance %s' % cmd)


@hosts(*INTEGRATION_HOSTS)
def kill_zeocache_integration():
    kill_zeocache()

@hosts(*STAGING_HOSTS)
def kill_zeocache_staging():
    kill_zeocache()

@hosts(*PRODUCTION_HOSTS)
def kill_zeocache():
    gfb('rm -f /tmp/instance-1.zec* /home/zope/gfb/parts/instance/var/instance2-2.zec*')

# The following functions carry the names of buildout profiles that are
# defined for OSHA together with post-processing code that performs
# system-wide installation and service restarts.

def nginx(base_profile, listen_address):
    with cd('/home/zope/gfb'):
        gfb('python nginxgenerator.py websites.py nginx-config %s %s %s '
             '> tmp/gfb.conf' % (
                listen_address[base_profile], base_profile,
                DNS_SUFFIX[base_profile]))
        gfb('sed -i -e "s/@VARNISH_ADDRESS@/%s/g" '
             '-e "s/@DELIVERANCE_ADDRESS@/%s/g" nginx-config/global.conf' % (
                VARNISH_ADDRESS[base_profile], DELIVERANCE_ADDRESS[base_profile]))
        sudo('rm -f /etc/nginx/sites-enabled/*', user='root')
        sudo('cp nginx-config/{global.conf,*.include} tmp/gfb.conf '
             '/etc/nginx/sites-enabled/', user='root')
        sudo('/etc/init.d/nginx reload', user='root')

def frontend(base_profile):
    nginx(base_profile, NGINX_ADDRESS)
    sudo('cp -u /home/zope/gfb/haproxy/haproxy-%s.cfg /etc/haproxy.cfg' %
         base_profile, user='root')
    sudo('/etc/init.d/haproxy reload', user='root')
    gfb('sed -i -e "s/@VARNISH_ADDRESS@/%s/g" '
         '/home/zope/gfb/varnish/conf.d_varnishd2.1' %
             VARNISH_ADDRESS[base_profile])
    sudo('cp -u /home/zope/gfb/varnish/conf.d_varnishd2.1 '
         '/etc/conf.d/varnishd2.1', user='root')
    sudo('cp -u /home/zope/gfb/varnish/default.vcl /etc/varnish/default.vcl',
         user='root')
    sudo('/etc/init.d/varnishd2.1 restart', user='root')

def multimedia(base_profile):
    nginx(base_profile, MEDIA_ADDRESS)

def ldap(base_profile):
    sudo('cp /home/zope/gfb/openldap/*.schema /etc/openldap/schema/', user='root')
    sudo('cp /home/zope/gfb/openldap/*.conf /etc/openldap/', user='root')
    sudo('/etc/init.d/slapd restart', user='root')

def zope(base_profile):
    gfb('cp -u /home/zope/gfb/nrpe.cfg /etc/nagios/nrpe/local/gfb.cfg')
    gfb('bin/instance restart')

def zeo(base_profile):
    gfb('etc/init.d/osha-zeo restart')

def solr(base_profile):
    gfb('bin/solr-instance restart')

#def deliverance(base_profile):
#    with cd('/home/zope'):
#        if not exists('/home/zope/deliverance'):
#            gfb('svn co %s deliverance' % deliverance_branch)
#        else:
#            with cd('deliverance'):
#                gfb('svn revert -R .')
#                gfb('svn switch %s' % deliverance_branch)
#                gfb('svn up')
#        with cd('deliverance/hw2010'):
#            gfb('sed s/localhost:8008/%s/ <etc/deliverance.xml '
#                 '> etc/deliverance-local.xml' % VARNISH_ADDRESS[base_profile])
#
#    gfb('/home/zope/gfb/bin/deliverance restart')

#def smartprintng_(base_profile):
#    if not exists('/home/zope/smartprintng'):
#        gfb('mkdir /home/zope/smartprintng')
#    if not exists('/home/zope/smartprintng/prince'):
#        with cd('/tmp/'):
#            gfb('tar xf /home/zope/gfb/3rdparty/prince-6.0r8-linux.tar.gz')
#        with cd('/tmp/prince-6.0r8-linux/'):
#            gfb('./install.sh <<EOF\n/home/zope/smartprintng/prince\nEOF\n')
#    with cd('/home/zope/smartprintng'):
#        gfb("echo -e '[buildout]\nextends = ../osha/profiles/production.cfg "
#             "../osha/profiles/base/smartprintng.cfg\n' > buildout.cfg")
#        gfb('cp /home/zope/gfb/bootstrap.py .')
#        if not exists('bin/buildout'):
#            gfb('python2.6 bootstrap.py --download-base=http://download.gocept.com/pypi/setuptools/')
#        gfb('bin/buildout')
#        gfb('bin/smartprint restart')

def memcache(base_profile):
    pass

#def birt(base_profile):
#    nginx(base_profile, BIRT_ADDRESS)
#    if not exists('/var/lib/tomcat-6/webapps/birt-viewer', use_sudo=True):
#        with cd('/tmp'):
#            run('wget -q http://ftp-stud.fht-esslingen.de/pub/Mirrors/eclipse/birt/downloads/drops/R-R1-2_6_1-201009171723/birt-runtime-2_6_1.zip')
#            run('unzip birt-runtime-2_6_1.zip')
#            run('rm birt-runtime-2_6_1.zip ')
#        with cd('/tmp/birt-runtime-2_6_1'):
#            sudo('cp -r WebViewerExample/ /var/lib/tomcat-6/webapps/birt-viewer')
#            run('rm -rf birt-runtime-2_6_1')
#            sudo('cp /usr/share/commons-logging/lib/*.jar /var/lib/tomcat-6/webapps/birt-viewer/WEB-INF/lib/')
#            sudo('cp /usr/share/jdbc-postgresql/lib/jdbc-postgresql.jar /var/lib/tomcat-6/webapps/birt-viewer/WEB-INF/lib/')
#
#    with cd('/var/lib/tomcat-6/webapps/birt-viewer'):
#        # check out the reports
#        if not exists('statistics', use_sudo=True):
#            sudo('svn co https://code.gocept.com/svn/osha/BIRT/trunk/ statistics')
#        with cd('statistics'):
#            sudo('svn revert -R .')
#            sudo('svn up')
#            sudo(r"sed -i -e 's/postgresql:\/\/birtserver\/global_portal_db/postgresql:\/\/%s\/%s/' *.rpt*"
#                 % (POSTGRES_SERVER[base_profile], 'osha'))
#            sudo(r"""sed -i -e 's/odaUser">postgres/odaUser">birt/' *.rpt*""")
#        if not exists('linkstats', use_sudo=True):
#            sudo('svn co https://code.gocept.com/svn/osha/BrokenLinkReporting/trunk/ linkstats')
#        with cd('linkstats'):
#            sudo('svn revert -R .')
#            sudo('svn up')
#            sudo(r"sed -i -e 's/postgresql:\/\/birtserver\/global_portal_db/postgresql:\/\/%s\/%s/' *.rpt*"
#                 % (POSTGRES_SERVER[base_profile], 'osha'))
#            sudo(r"""sed -i -e 's/odaUser">postgres/odaUser">birt/' *.rpt*""")
#        sudo('chown -R tomcat: .')
#        try:
#            sudo('/etc/init.d/tomcat-6 stop')
#        except:
#            time.sleep(5)
#            sudo('/etc/init.d/tomcat-6 zap')
#        sudo('/etc/init.d/tomcat-6 start')

#def lms(base_profile):
#    BUILDOUT_TEMPLATE = """[buildout]
#allow-picked-versions = false
#extends = profiles/base.cfg /home/zope/secrets.cfg
#parts += lms-cron-zeo lms-cron-pack lms-cron-web lms-cron-checker
#         lms-cron-scheduler lms-cron-notifier lms-cron-syncer
#
#[versions]
#zc.buildout = 1.5.2
#z3c.recipe.tag = 0.3
#gocept.lms = 3.0a6
#z3c.recipe.usercrontab = 1.1
#
#[app]
#admin-password = ${passwords:lms-admin}
#appname = lms
#mail-server-host = mail.gocept.net
#lms-email-address = support@gocept.com
#lms-name = OSHA lms
#lms-xmlrpc-address = http://%(host)s.gocept.net:8081/lms
#
#[zeo]
#host = localhost
#port = 8099
#address = ${zeo:host}:${zeo:port}
#
#[web]
#address = %(host)s:8081
#
#[reboot]
#recipe = z3c.recipe.usercrontab
#times = @reboot
#
#[lms-cron-zeo]
#<= reboot
#command = ${buildout:parts-directory}/deployment/etc/init.d/lms-zeo start |& logger -t lms.zeo
#
#[lms-cron-web]
#<= reboot
#command = ${buildout:parts-directory}/deployment/etc/init.d/lms-web start |& logger -t lms.web
#
#[lms-cron-checker]
#<= reboot
#command = ${buildout:parts-directory}/deployment/etc/init.d/lms-checker start |& logger -t lms.checker
#
#[lms-cron-scheduler]
#<= reboot
#command = ${buildout:parts-directory}/deployment/etc/init.d/lms-scheduler start |& logger -t lms.scheduler
#
#[lms-cron-notifier]
#<= reboot
#command = ${buildout:parts-directory}/deployment/etc/init.d/lms-notifier start |& logger -t lms.notifier
#
#[lms-cron-syncer]
#<= reboot
#command = ${buildout:parts-directory}/deployment/etc/init.d/lms-syncer start |& logger -t lms.syncer
#
#[lms-cron-pack]
#recipe = z3c.recipe.usercrontab
#times = 47 2 * * *
#command = ${buildout:directory}/bin/zeopack -h ${zeo:host} -p ${zeo:port} -d 1 |& logger -t lms.zeopack
#
#"""
#    if not exists('/home/zope/lms'):
#        gfb('svn co https://code.gocept.com/svn/gocept/gocept.lms/deployment /home/zope/lms')
#    with cd('/home/zope/lms'):
#        gfb('svn revert -R .')
#        buildout = BUILDOUT_TEMPLATE % dict(host=env.host)
#        gfb("echo -e '%s' > buildout.cfg" % buildout)
#        gfb("python2.4 bootstrap.py")
#        gfb("bin/buildout")
#        gfb("parts/deployment/etc/init.d/lms-zeo restart")
#        gfb("parts/deployment/etc/init.d/lms-web restart")
#        gfb("parts/deployment/etc/init.d/lms-checker restart")
#        gfb("parts/deployment/etc/init.d/lms-scheduler restart")
#        gfb("parts/deployment/etc/init.d/lms-syncer restart")
#        gfb("parts/deployment/etc/init.d/lms-notifier restart")

#def awstats(base_profile):
#    # config
#    gfb('python awstatsgenerator.py websites.py %s %s > tmp/pages.cfg' % (
#            base_profile, DNS_SUFFIX[base_profile]))
#    sudo('install awstats/conf/* tmp/pages.cfg /etc/awstats/', user='root')
#    sudo('install -m0755 awstats/bin/* /etc/awstats/', user='root')
#    # reports utility
#    with cd('/home/zope'):
#        if not exists('/home/zope/awstatsreport'):
#            gfb('svn co %s awstatsreport' % awstatsreport_branch)
#            with cd('awstatsreport'):
#                gfb('virtualenv-2.6 --no-site-packages .')
#                gfb('./bin/python2.6 bootstrap.py')
#        else:
#            with cd('awstatsreport'):
#                gfb('svn revert -R .')
#                gfb('svn switch %s' % awstatsreport_branch)
#                gfb('svn up')
#        with cd('awstatsreport'):
#            gfb('./bin/buildout')
#            gfb('./bin/instance restart || ./bin/instance start')
#    sudo(('cp -u awstats/apache.conf '
#          '/etc/apache2/vhosts.d/%s.gocept.net.local.include' %
#          env.host), user='root')
#    sudo('cp -u awstats/local.inc /srv/www/localhost/htdocs/awstats/local.inc',
#         user='root')
#    sudo('install -d -o osha /srv/www/awstats/reports', user='root')
#    sudo('/etc/init.d/apache2 reload')

def calendarfetcher(base_profile):
    pass


# Per-machine settings. These settings are divided by staging (oshawebtest)
# and production (oshaweb). The machine roles in the testing are a bit more
# compressed so individual machines carry more roles than in the production.

settings = {}

# Integration machine settings
settings['ext5'] = dict(profiles=[ldap, memcache, solr, zeo], pyver='2.5')
settings['ext6'] = dict(profiles=[frontend, zope, deliverance, awstats, calendarfetcher, multimedia])

# Staging machine settings
settings['oshawebtest00'] = dict(profiles=[frontend, deliverance, awstats])
settings['oshawebtest01'] = dict(profiles=[zope, calendarfetcher])
settings['oshawebtest02'] = dict(profiles=[zope])
settings['oshawebtest03'] = dict(profiles=[zeo, ldap, multimedia, memcache],
                                 pyver='2.5')
settings['oshawebtest04'] = dict(profiles=[solr, smartprintng_, birt, lms])

# Production machine settings

settings['oshaweb00'] = dict(profiles=[frontend, awstats])
settings['oshaweb01'] = dict(profiles=[zope, calendarfetcher],
                             buildout='[instance]\nzserver-threads=10\n')
settings['oshaweb02'] = dict(profiles=[zope],
                             buildout='[instance]\nzserver-threads=10\n')
settings['oshaweb03'] = dict(profiles=[zope])
settings['oshaweb04'] = dict(profiles=[zope])
settings['oshaweb05'] = dict(profiles=[zope])
settings['oshaweb06'] = dict(profiles=[zope])
settings['oshaweb07'] = dict(profiles=[zope])
settings['oshaweb08'] = dict(profiles=[zope])
settings['oshaweb09'] = dict(profiles=[zope])
settings['oshaweb10'] = dict(profiles=[zope])
settings['oshaweb11'] = dict(profiles=[zope])
settings['oshaweb12'] = dict(profiles=[zope])
settings['oshaweb13'] = dict(profiles=[zope])
settings['oshaweb14'] = dict(profiles=[zope])
settings['oshaweb15'] = dict(profiles=[zope])
settings['oshaweb16'] = dict(profiles=[zope])
settings['oshaweb17'] = dict(profiles=[zope])
settings['oshaweb18'] = dict(profiles=[zope])
settings['oshaweb19'] = dict(profiles=[zope])
settings['oshaweb20'] = dict(profiles=[zope])
settings['oshaweb21'] = dict(profiles=[zeo, ldap], pyver='2.5')
settings['oshaweb22'] = dict(profiles=[multimedia])
settings['oshaweb23'] = dict(profiles=[smartprintng_, birt, lms])
settings['oshaweb24'] = dict(profiles=[solr])
settings['oshaweb25'] = dict(profiles=[memcache])   # memcache only
settings['oshaweb26'] = dict(profiles=[deliverance])


# Fabric deployment helpers

def gfb(cmd):
    sudo(cmd, user='zope')

def deploy(base_profile):
    setting = settings[env.host.replace(DOMAIN_SUFFIX[base_profile], '')]

    with cd('/home/zope'):
        if not exists('/home/zope/gfb'):
            gfb('svn co %s gfb' % branch)
        else:
            with cd('gfb'):
                gfb('svn revert -R .')
                gfb('svn switch %s' % branch)
                gfb('svn up')

    with cd('/home/zope/gfb'):
        extends = []
        parts = []
        for profile in setting['profiles']:
            extends.append('profiles/base/%s.cfg' % profile.__name__)
            parts.append('${buildout:%s-parts}' % profile.__name__)
        extends.append('profiles/%s.cfg' % base_profile)
        extends = ' '.join(extends)
        parts = ' '.join(parts)
        gfb("echo -e '[buildout]\nextends = %s\nparts = %s' > buildout.cfg" %
             (extends, parts))
        if not exists('bin/buildout'):
            gfb('python%s bootstrap.py --download-base=%s' %
                 (setting.get('pyver', '2.4'), PYPI))
        gfb('bin/buildout')
        for profile in setting.get('profiles', []):
            profile(base_profile)
        gfb('cp -u logrotate.master.conf /var/spool/logrotate/gfb')
