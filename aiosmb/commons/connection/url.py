import enum
from urllib.parse import urlparse, parse_qs
from aiosmb.commons.connection.credential import SMBCredential, SMBCredentialsSecretType, SMBAuthProtocol
from aiosmb.commons.connection.targetproxy import SMBTargetProxy
from aiosmb.commons.connection.target import SMBTarget, SMBConnectionDialect, SMBConnectionProtocol


class SMBConnectionURL:
	def __init__(self, connection_url):
		self.connection_url = connection_url
		
		#credential
		self.authentication_protocol = None
		self.secret_type = None
		self.domain = None
		self.username = None
		self.secret = None
		self.is_anonymous = None
		self.auth_settings = {}

		#target
		self.dialect = None
		self.protocol = None
		self.hostname = None
		self.dc_ip = None
		self.port = None
		self.ip = None
		self.timeout = 5

		#proxy
		self.proxy= None

		self.parse()

	def get_proxy(self):
		return self.proxy

	def get_target(self):
		return SMBTarget(
			ip = self.ip, 
			port = self.port, 
			hostname = self.hostname, 
			timeout = self.timeout, 
			dc_ip= self.dc_ip, 
			domain = self.domain, 
			proxy = self.get_proxy()
		)

	def get_credential(self):
		return SMBCredential(
			username = self.username,
			domain = self.domain, 
			secret = self.secret, 
			secret_type = self.secret_type, 
			authentication_type = self.authentication_protocol, 
			settings = self.auth_settings,
			target = self.ip
		)
	

	def scheme_decoder(self, scheme):
		#print('SCHEME: %s' % scheme)
		schemes = scheme.upper().split('+')
		
		connection_tags = schemes[0].split('-')
		if len(connection_tags) > 1:
			self.dialect = SMBConnectionDialect(connection_tags[0])
			self.protocol = SMBConnectionProtocol(connection_tags[1])
		else:
			self.dialect = SMBConnectionDialect(connection_tags[0])
			self.protocol = SMBConnectionProtocol.TCP

		if len(schemes) == 1:
			self.authentication_protocol = SMBAuthProtocol.NTLM
			self.secret_type = SMBCredentialsSecretType.NONE
			return

		auth_tags = schemes[1].split('-')
		#print(auth_tags)
		if len(auth_tags) > 1:
			if auth_tags[0] == 'MULTIPLEXOR':
				if auth_tags[1] == 'SSL':
					if len(auth_tags) == 2:
						self.authentication_protocol = SMBAuthProtocol.MULTIPLEXOR_SSL_NTLM
					else:
						if auth_tags[2] == 'NTLM':
							self.authentication_protocol = SMBAuthProtocol.MULTIPLEXOR_SSL_NTLM
						elif auth_tags[2] == 'KERBEROS':
							self.authentication_protocol = SMBAuthProtocol.MULTIPLEXOR_SSL_KERBEROS
				else:
					if auth_tags[1] == 'NTLM':
						self.authentication_protocol = SMBAuthProtocol.MULTIPLEXOR_NTLM
					elif auth_tags[1] == 'KERBEROS':
						self.authentication_protocol = SMBAuthProtocol.MULTIPLEXOR_KERBEROS
			else:
				self.authentication_protocol = SMBAuthProtocol(auth_tags[0])
				self.secret_type = SMBCredentialsSecretType(auth_tags[1])
		else:
			if auth_tags[0] == 'MULTIPLEXOR':
				self.authentication_protocol = SMBAuthProtocol.MULTIPLEXOR_NTLM
			elif auth_tags[0] == 'MULTIPLEXOR_SSL':
				self.authentication_protocol = SMBAuthProtocol.MULTIPLEXOR_SSL_NTLM
			else:
				self.authentication_protocol = SMBAuthProtocol(auth_tags[0])
			if self.authentication_protocol == SMBAuthProtocol.KERBEROS:
				raise Exception('For kerberos auth you need to specify the secret type in the connection string!')


	def parse(self):
		url_e = urlparse(self.connection_url)
		self.scheme_decoder(url_e.scheme)
		
		if url_e.username is not None:
			if url_e.username.find('\\') != -1:
				self.domain , self.username = url_e.username.split('\\')
			else:
				self.domain = None
				self.username = url_e.username
		
		self.secret = url_e.password
		if self.secret is None and self.username is None:
			self.is_anonymous = True
		
		if self.authentication_protocol == SMBAuthProtocol.NTLM and self.secret_type is None:
			if self.is_anonymous == True:
				self.secret_type = SMBCredentialsSecretType.NONE
			else:
				if len(self.secret) == 32:
					try:
						bytes.fromhex(self.secret)
					except:
						self.secret_type = SMBCredentialsSecretType.NT
					else:
						self.secret_type = SMBCredentialsSecretType.PASSWORD

		elif self.authentication_protocol in [SMBAuthProtocol.SSPI_KERBEROS, SMBAuthProtocol.SSPI_NTLM, 
												SMBAuthProtocol.MULTIPLEXOR_NTLM, SMBAuthProtocol.MULTIPLEXOR_KERBEROS]:
			if self.username is None:
				self.username = '<CURRENT>'
			if self.domain is None:
				self.domain = '<CURRENT>'
			if self.secret is None:
				self.secret = '<CURRENT>'


		self.ip = url_e.hostname
		if url_e.port:
			self.port = url_e.port
		elif self.protocol == SMBConnectionProtocol.TCP:
			self.port = 445
		else:
			raise Exception('Port must be provided!')

		# recognized parameters :
		# dc -> domain controller IP
		# proxytype -> proxy protocol
		# proxyuser -> username for proxy auth
		# proxypass -> password for proxy auth
		#  
		#
		if url_e.query is not None:
			query = parse_qs(url_e.query)
			for k in query:
				if k == 'dc':
					self.dc_ip = query[k][0]
				elif k == 'timeout':
					self.timeout = int(query[k][0])
				elif k == 'dns':
					self.dns = query[k] #multiple dns can be set, so not trimming here
				elif k.startswith('auth'):
					self.auth_settings[k[len('auth'):]] = query[k]
		
		self.proxy = SMBTargetProxy.from_url(self.connection_url)
			
if __name__ == '__main__':
	url_tests = [
		#'smb://10.10.10.2',
		#'smb://10.10.10.2:9000',
		#'smb-tcp://10.10.10.2',
		#'smb-tcp://10.10.10.2:9000',
		#'smb-udp://10.10.10.2:138',
		#'smb+ntlm-password://domain\\user@10.10.10.2',
		#'smb-tcp+ntlm-password://domain\\user:password@10.10.10.2',
		#'smb-tcp+ntlm-password://domain\\user:password@10.10.10.2:10000',
		#'smb-tcp+ntlm-nt://domain\\user:alma@10.10.10.2',
		#'smb+ntlm-nt://domain\\user:alma@10.10.10.2',
		#'smb+ntlm-nt://domain\\user:alma@10.10.10.2',
		#'smb-tcp+kerberos-password://domain\\alma:password@10.10.10.10.2',
		#'smb-tcp+kerberos-aes://domain\\alma:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@10.10.10.10.2',
		#'smb-tcp+kerberos-aes://domain\\alma:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@10.10.10.10.2',
		#'smb-tcp+kerberos-nt://domain\\alma:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@10.10.10.10.2',
		#'smb-tcp+kerberos-rc4://domain\\alma:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa@10.10.10.10.2',
		#'smb+sspi://10.10.10.10.2',
		#'smb+sspi-ntlm://10.10.10.10.2',
		#'smb+sspi-kerberos://10.10.10.10.2',
		#'smb+multiplexor://10.10.10.10.2',
		#'smb+multiplexor-ssl://10.10.10.10.2',
		#'smb+multiplexor-ssl-ntlm://10.10.10.10.2',
		#'smb+multiplexor-ssl-kerberos://10.10.10.10.2',
		'smb://10.10.10.2/?timeout=10',
		'smb://10.10.10.2/?timeout=10&dc=10.10.10.2',
		'smb://10.10.10.2/?timeout=10&dc=10.10.10.2&proxytype=socks5',
		'smb://10.10.10.2/?timeout=10&dc=10.10.10.2&proxytype=socks5&proxyserver=127.0.0.1',
		'smb://10.10.10.2/?timeout=10&dc=10.10.10.2&proxytype=socks5&proxyserver=127.0.0.1&proxyuser=admin&proxypass=alma',
		'smb://10.10.10.2/?timeout=10&dc=10.10.10.2&proxytype=socks5&proxyserver=127.0.0.1&proxyuser=admin&proxypass=alma&dc=10.10.10.2&dns=8.8.8.8',
		'smb://10.10.10.2/?timeout=10&dc=10.10.10.2&proxytype=socks5-ssl&proxyserver=127.0.0.1&proxyuser=admin&proxypass=alma&dc=10.10.10.2&dns=8.8.8.8',
		'smb://10.10.10.2/?timeout=10&dc=10.10.10.2&proxytype=multiplexor&proxyserver=127.0.0.1',
		'smb://10.10.10.2/?timeout=10&dc=10.10.10.2&proxytype=multiplexor&proxyserver=127.0.0.1&proxyagentid=alma',
		'smb://10.10.10.2/?timeout=10&dc=10.10.10.2&proxytype=multiplexor&proxyserver=127.0.0.1&proxyagentid=alma&proxytimeout=111',

	]
	for url in url_tests:
		print('===========================================================================')
		print(url)
		try:
			dec = SMBConnectionURL(url)
			creds = dec.get_credential()
			target = dec.get_target()
		except Exception as e:
			import traceback
			traceback.print_exc()
			print('ERROR! Reason: %s' % e)
			input()
		else:
			print(str(creds))
			print(str(target))
			input()
			
			
