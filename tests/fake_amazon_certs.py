"""Made-up certificates shaped like Amazon's Alexa signing chain, for tests (no network).

A root CA, an intermediate CA and a signing certificate for `echo-api.amazon.com`, all
generated here, plus helpers to sign request bodies the way Alexa does.
"""

import base64
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

NOW = datetime(2026, 10, 11, 10, 0, tzinfo=UTC)
ECHO_HOST = "echo-api.amazon.com"


def _key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _ca(
    name: str,
    key: rsa.RSAPrivateKey,
    issuer: x509.Name,
    issuer_key: rsa.RSAPrivateKey,
    start: datetime,
    end: datetime,
) -> x509.Certificate:
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(name))
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(end)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),
            critical=False,
        )
    )
    return builder.sign(issuer_key, hashes.SHA256())


def _leaf(
    hosts: list[str],
    key: rsa.RSAPrivateKey,
    issuer: x509.Name,
    issuer_key: rsa.RSAPrivateKey,
    start: datetime,
    end: datetime,
) -> x509.Certificate:
    builder = (
        x509.CertificateBuilder()
        .subject_name(_name(hosts[0] if hosts else "nobody"))
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(start)
        .not_valid_after(end)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.SERVER_AUTH, ExtendedKeyUsageOID.CLIENT_AUTH]
            ),
            critical=False,
        )
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()),
            critical=False,
        )
    )
    if hosts:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(host) for host in hosts]), critical=False
        )
    return builder.sign(issuer_key, hashes.SHA256())


def pem(*certs: x509.Certificate) -> bytes:
    """Certificates as one PEM chain, signing certificate first."""
    return b"".join(cert.public_bytes(serialization.Encoding.PEM) for cert in certs)


@dataclass
class FakeAmazon:
    """A made-up Alexa signing chain and its keys."""

    root: x509.Certificate
    intermediate: x509.Certificate
    leaf: x509.Certificate
    root_key: rsa.RSAPrivateKey
    intermediate_key: rsa.RSAPrivateKey
    leaf_key: rsa.RSAPrivateKey

    @property
    def chain(self) -> bytes:
        """The PEM chain Alexa's cert URL would give: signing cert, then intermediate."""
        return pem(self.leaf, self.intermediate)

    def sign(self, body: bytes, key: rsa.RSAPrivateKey | None = None) -> str:
        """The `Signature-256` header for `body`."""
        signature = (key or self.leaf_key).sign(body, padding.PKCS1v15(), hashes.SHA256())
        return base64.b64encode(signature).decode()

    def leaf_for(
        self,
        hosts: list[str],
        start: datetime | None = None,
        end: datetime | None = None,
        issuer_key: rsa.RSAPrivateKey | None = None,
    ) -> x509.Certificate:
        """Another signing certificate under the intermediate, using the same key."""
        return _leaf(
            hosts,
            self.leaf_key,
            self.intermediate.subject,
            issuer_key or self.intermediate_key,
            start or NOW - timedelta(days=30),
            end or NOW + timedelta(days=30),
        )


def make_fake_amazon() -> FakeAmazon:
    """A fresh made-up chain valid for 30 days either side of NOW."""
    root_key, intermediate_key, leaf_key = _key(), _key(), _key()
    start, end = NOW - timedelta(days=365), NOW + timedelta(days=365)
    root = _ca("Fake Root CA", root_key, _name("Fake Root CA"), root_key, start, end)
    intermediate = _ca("Fake Intermediate CA", intermediate_key, root.subject, root_key, start, end)
    leaf = _leaf(
        [ECHO_HOST],
        leaf_key,
        intermediate.subject,
        intermediate_key,
        NOW - timedelta(days=30),
        NOW + timedelta(days=30),
    )
    return FakeAmazon(root, intermediate, leaf, root_key, intermediate_key, leaf_key)
