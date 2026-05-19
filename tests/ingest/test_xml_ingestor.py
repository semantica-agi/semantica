from pathlib import Path

import pytest

from semantica.ingest import (
    XMLIngestionData,
    XMLIngestor,
    ingest,
    ingest_file,
    ingest_xml,
)
from semantica.ingest.xml_ingestor import XML_NAMESPACE
from semantica.utils.exceptions import ProcessingError, ValidationError


def test_xml_ingestor_extracts_structure_namespaces_and_attributes(
    tmp_path: Path,
) -> None:
    xml_file = tmp_path / "catalog.xml"
    xml_file.write_text(
        """<?xml version="1.0"?>
<catalog xmlns="https://example.com/catalog" xmlns:bk="https://example.com/book">
  <bk:book id="b1" xml:lang="en">
    <title>Semantica</title>
    <bk:author role="lead">Ada</bk:author>
  </bk:book>
</catalog>
""",
        encoding="utf-8",
    )

    data = XMLIngestor().ingest_file(xml_file)

    assert isinstance(data, XMLIngestionData)
    assert data.root_tag == "catalog"
    assert data.namespaces["default"] == "https://example.com/catalog"
    assert data.namespaces["bk"] == "https://example.com/book"
    assert data.namespaces["xml"] == XML_NAMESPACE
    assert data.root["children"][0]["tag"] == "bk:book"
    assert data.root["children"][0]["attributes"]["id"] == "b1"
    assert data.root["children"][0]["attribute_details"]["xml:lang"]["value"] == "en"
    assert (
        data.root["children"][0]["attribute_details"]["xml:lang"]["namespace"]
        == XML_NAMESPACE
    )
    assert data.elements[0]["tag"] == "catalog"
    assert data.elements[1]["tag"] == "bk:book"
    assert data.metadata["element_count"] == 4
    assert data.metadata["attribute_count"] == 3
    assert data.metadata["root_namespace"] == "https://example.com/catalog"
    assert data.metadata["tag_counts"]["bk:author"] == 1


def test_xml_ingestor_validates_xsd_schema(tmp_path: Path) -> None:
    xml_file = tmp_path / "catalog.xml"
    xml_file.write_text(
        """<catalog>
  <book id="b1">
    <title>Semantica</title>
  </book>
</catalog>
""",
        encoding="utf-8",
    )
    xsd_file = tmp_path / "catalog.xsd"
    xsd_file.write_text(
        """<?xml version="1.0"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="catalog">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="book" maxOccurs="unbounded">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="title" type="xs:string"/>
            </xs:sequence>
            <xs:attribute name="id" type="xs:string" use="required"/>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
""",
        encoding="utf-8",
    )

    data = XMLIngestor().ingest_file(xml_file, schema_path=xsd_file)

    assert data.validation["is_valid"] is True
    assert data.validation["schema"]["validated"] is True
    assert data.validation["schema"]["valid"] is True


def test_xml_ingestor_reports_schema_validation_errors(tmp_path: Path) -> None:
    xml_file = tmp_path / "catalog.xml"
    xml_file.write_text("<catalog><book id='b1'/></catalog>", encoding="utf-8")
    xsd_file = tmp_path / "catalog.xsd"
    xsd_file.write_text(
        """<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:element name="catalog">
    <xs:complexType>
      <xs:sequence>
        <xs:element name="book">
          <xs:complexType>
            <xs:sequence>
              <xs:element name="title" type="xs:string"/>
            </xs:sequence>
            <xs:attribute name="id" type="xs:string" use="required"/>
          </xs:complexType>
        </xs:element>
      </xs:sequence>
    </xs:complexType>
  </xs:element>
</xs:schema>
""",
        encoding="utf-8",
    )

    report = XMLIngestor().validate_file(xml_file, schema_path=xsd_file)

    assert report["is_valid"] is False
    assert report["schema"]["validated"] is True
    assert report["schema"]["valid"] is False
    assert report["schema"]["errors"]

    with pytest.raises(ValidationError, match="XML schema validation failed"):
        XMLIngestor().ingest_file(xml_file, schema_path=xsd_file)


def test_xml_ingestor_validates_internal_dtd(tmp_path: Path) -> None:
    xml_file = tmp_path / "note.xml"
    xml_file.write_text(
        """<!DOCTYPE note [
<!ELEMENT note (to,from)>
<!ELEMENT to (#PCDATA)>
<!ELEMENT from (#PCDATA)>
]>
<note><to>Ada</to><from>Grace</from></note>
""",
        encoding="utf-8",
    )

    report = XMLIngestor().validate_file(xml_file, validate_dtd=True)

    assert report["is_valid"] is True
    assert report["dtd"]["validated"] is True
    assert report["dtd"]["valid"] is True
    assert report["dtd"]["name"] == "note"


def test_xml_ingestor_rejects_malformed_xml(tmp_path: Path) -> None:
    xml_file = tmp_path / "broken.xml"
    xml_file.write_text("<root><item></root>", encoding="utf-8")

    with pytest.raises(ProcessingError, match="Malformed XML"):
        XMLIngestor().ingest_file(xml_file)


def test_xml_ingest_methods_and_unified_dispatch(tmp_path: Path) -> None:
    xml_file = tmp_path / "catalog.xml"
    xml_file.write_text(
        "<catalog><book id='b1'>Semantica</book></catalog>",
        encoding="utf-8",
    )

    direct = ingest_xml(xml_file)
    metadata = ingest_xml(xml_file, method="metadata")
    via_file_method = ingest_file(xml_file, method="xml")
    unified = ingest(xml_file)

    assert isinstance(direct, XMLIngestionData)
    assert metadata["root_tag"] == "catalog"
    assert isinstance(via_file_method, XMLIngestionData)
    assert isinstance(unified["xml"], XMLIngestionData)


def test_xml_ingestor_ingests_string() -> None:
    data = XMLIngestor().ingest_string("<root><item id='1'>hello</item></root>")

    assert isinstance(data, XMLIngestionData)
    assert data.root_tag == "root"
    assert data.metadata["source_type"] == "string"
    assert data.elements[1]["attributes"]["id"] == "1"
    assert data.elements[1]["text"] == "hello"


def test_xml_ingestor_ingests_directory(tmp_path: Path) -> None:
    (tmp_path / "one.xml").write_text("<root><one /></root>", encoding="utf-8")
    (tmp_path / "two.xml").write_text("<root><two /></root>", encoding="utf-8")
    (tmp_path / "skip.txt").write_text("<root />", encoding="utf-8")

    results = ingest_xml(tmp_path, method="directory", recursive=False)

    assert len(results) == 2
    assert {result.metadata["file_name"] for result in results} == {
        "one.xml",
        "two.xml",
    }
