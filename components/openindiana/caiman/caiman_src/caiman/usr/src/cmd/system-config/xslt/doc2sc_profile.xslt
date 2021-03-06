<?xml version="1.0" encoding="UTF-8"?>

<!--
 CDDL HEADER START

 The contents of this file are subject to the terms of the
 Common Development and Distribution License (the "License").
 You may not use this file except in compliance with the License.

 You can obtain a copy of the license at usr/src/OPENSOLARIS.LICENSE
 or http://www.opensolaris.org/os/licensing.
 See the License for the specific language governing permissions
 and limitations under the License.

 When distributing Covered Code, include this CDDL HEADER in each
 file and include the License file at usr/src/OPENSOLARIS.LICENSE.
 If applicable, add the following below this CDDL HEADER, with the
 fields enclosed by brackets "[]" replaced with your own identifying
 information: Portions Copyright [yyyy] [name of copyright owner]

 CDDL HEADER END

 Copyright (c) 2011, Oracle and/or its affiliates. All rights reserved.
-->

<!-- Restructure the contents of the DataObjectCache to -->
<!-- resemble a System Configuration Profile: -->
<!-- - add a reference to the external DTD -->
<!-- - take the service_bundle element(s) from anywhere in -->
<!--   the cache (there should only be one) and output them, -->
<!--   unmodified and in their entirety -->

<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="1.0">
    <xsl:output method="xml" indent="yes" encoding="UTF-8" doctype-system="/usr/share/lib/xml/dtd/service_bundle.dtd.1"/>

    <xsl:template match="/">
        <xsl:copy-of select="//service_bundle[@name='sysconfig']"/>
    </xsl:template> 
</xsl:stylesheet>
