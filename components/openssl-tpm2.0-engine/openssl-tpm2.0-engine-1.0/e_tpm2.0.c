/*
 * Copyright 2017 Pluribus Networks Inc.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *    http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */
#include <stdio.h>
#include <string.h>
#include <pthread.h>

#include <openssl/asn1t.h>
#include <openssl/pem.h>
#include <openssl/engine.h>

#include <tss2/tss.h>
#include <tss2/tssmarshal.h>

#include "e_tpm2.0_err.h"

static const char *engine_id = "tpm2.0";
static const char *engine_name = "TPM2.0 hardware engine support";
static pthread_mutex_t e_tpm_mutex;

typedef struct {
	TPM_HANDLE	pri_key_obj_hnd;
	TPM2B_PUBLIC	pri_key_pub;
} E_TPM2DOT0_GL_CTX;

typedef struct {
	TPM_HANDLE	ch_key_obj_hnd;
	TPM2B_PRIVATE	ch_key_priv;
	TPM2B_PUBLIC	ch_key_pub;
} E_TPM2DOT0_RSA_CTX;

typedef struct {
	int		nbits;
	int		pad_mode;
	const EVP_MD	*md;
} E_TPM2DOT0_PKEY_CTX;


E_TPM2DOT0_GL_CTX	*tpm2dot_gctx = NULL;

static int
tpm2dot0_startup(void)
{
	TPM_RC		rc;
	TSS_CONTEXT	*tss_ctx = NULL;
	Startup_In	in = { 0 };
	int		ret = 0;

	rc = TSS_Create(&tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_STARTUP,
		    TPM2DOT0_R_TSS_CREATE_ERROR);
		return (-1);
	}

	in.startupType = TPM_SU_CLEAR;
	rc = TSS_Execute(tss_ctx, NULL,
	    (COMMAND_PARAMETERS *)&in, NULL,
	    TPM_CC_Startup, TPM_RH_NULL, NULL, 0);

	if (rc != 0 && rc != TPM_RC_INITIALIZE) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_STARTUP,
		    TPM2DOT0_R_TPM__CC__STARTUP_ERROR);
		ret = -1;
	}

	rc = TSS_Delete(tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_STARTUP,
		    TPM2DOT0_R_TSS_DELETE_ERROR);
		ret = -1;
	}

	return (ret);
}

static int
tpm2dot0_get_capability(GetCapability_In *in, GetCapability_Out *out)
{
	TPM_RC		rc;
	TSS_CONTEXT	*tss_ctx = NULL;

	rc = TSS_Create(&tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_GET_CAPABILTY,
		    TPM2DOT0_R_TSS_CREATE_ERROR);
		return (-1);
	}

	rc = TSS_Execute(tss_ctx,
	    (RESPONSE_PARAMETERS *)out,
	    (COMMAND_PARAMETERS *)in,
	    NULL, TPM_CC_GetCapability,
	    TPM_RH_NULL, NULL, 0);

	rc = TSS_Delete(tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_GET_CAPABILTY,
		    TPM2DOT0_R_TSS_DELETE_ERROR);
		return (-1);
	}

	return (0);
}

static int
tpm2dot0_flush_context(TPMI_DH_CONTEXT handle)
{
	TPM_RC		rc;
	TSS_CONTEXT	*tss_ctx = NULL;
	FlushContext_In	in = { 0 };

	rc = TSS_Create(&tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_FLUSH_CONTEXT,
		    TPM2DOT0_R_TSS_CREATE_ERROR);
		return (-1);
	}

	in.flushHandle = handle;
	rc = TSS_Execute(tss_ctx,
	    NULL, (COMMAND_PARAMETERS *)&in, NULL,
	    TPM_CC_FlushContext, TPM_RH_NULL, NULL, 0);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_FLUSH_CONTEXT,
		    TPM2DOT0_R_TPM__CC__FLUSHCONTEXT_ERROR);
		return (-1);
	}

	rc = TSS_Delete(tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_FLUSH_CONTEXT,
		    TPM2DOT0_R_TSS_DELETE_ERROR);
		return (-1);
	}

	return (0);
}

static int
tpm2dot0_flush_all_handles(void)
{
	GetCapability_In	in = { 0 };
	GetCapability_Out	out = { 0 };
	uint32_t		count;
	TPML_HANDLE		*handles;

	in.capability = TPM_CAP_HANDLES;
	in.property = HR_TRANSIENT;
	in.propertyCount = sizeof (TPMS_CAPABILITY_DATA) / sizeof (TPM_HANDLE);

	if (tpm2dot0_get_capability(&in, &out) != 0) {
		return (-1);
	}

	handles = (TPML_HANDLE *)&out.capabilityData.data;
	for (count = 0; count < handles->count; count++) {
		if (tpm2dot0_flush_context(handles->handle[count]) != 0) {
			return (-1);
		}
	}

	return (0);
}

static int
tpm2dot0_create_pri_ek(void)
{
	TPM_RC			rc;
	TSS_CONTEXT		*tss_ctx = NULL;
	CreatePrimary_In	in = { 0 };
	CreatePrimary_Out	out = { 0 };
	TPMI_SH_AUTH_SESSION	sess_hnd = TPM_RS_PW;
	const char		*passwd = NULL;
	unsigned int		sess_attr = 0;

	rc = TSS_Create(&tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CREATE_PRI_EK,
		    TPM2DOT0_R_TSS_CREATE_ERROR);
		return (-1);
	}

	in.primaryHandle = TPM_RH_ENDORSEMENT;

	in.inSensitive.t.sensitive.userAuth.t.size = 0;
	in.inSensitive.t.sensitive.data.t.size = 0;

	in.inPublic.t.publicArea.type = TPM_ALG_RSA;
	in.inPublic.t.publicArea.nameAlg = TPM_ALG_SHA256;

	in.inPublic.t.publicArea.objectAttributes.val = 0;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_FIXEDTPM;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_FIXEDPARENT;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_SENSITIVEDATAORIGIN;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_USERWITHAUTH;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_NODA;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_RESTRICTED;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_DECRYPT;

	in.inPublic.t.publicArea.authPolicy.t.size = 0;

	in.inPublic.t.publicArea.parameters.rsaDetail.symmetric.algorithm = TPM_ALG_AES;
	in.inPublic.t.publicArea.parameters.rsaDetail.symmetric.keyBits.aes = 128;
	in.inPublic.t.publicArea.parameters.rsaDetail.symmetric.mode.aes = TPM_ALG_CFB;
	in.inPublic.t.publicArea.parameters.rsaDetail.scheme.scheme = TPM_ALG_NULL;
	in.inPublic.t.publicArea.parameters.rsaDetail.keyBits = 2048;
	in.inPublic.t.publicArea.parameters.rsaDetail.exponent = 0;

	in.inPublic.t.publicArea.unique.rsa.t.size = 0;

	in.outsideInfo.t.size = 0;

	in.creationPCR.count = 0;

	rc = TSS_Execute(tss_ctx,
	    (RESPONSE_PARAMETERS *)&out, (COMMAND_PARAMETERS *)&in, NULL,
	    TPM_CC_CreatePrimary, sess_hnd, passwd,
	    sess_attr, TPM_RH_NULL, NULL, 0);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CREATE_PRI_EK,
		    TPM2DOT0_R_TPM__CC__CREATEPRIMARY_ERROR);
		return (-1);
	}

	tpm2dot_gctx->pri_key_obj_hnd = out.objectHandle;
	tpm2dot_gctx->pri_key_pub = out.outPublic;

	rc = TSS_Delete(tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CREATE_PRI_EK,
		    TPM2DOT0_R_TSS_DELETE_ERROR);
		return (-1);
	}

	return (0);
}

static int
tpm2dot0_flush_pri_ek(void)
{
	return (tpm2dot0_flush_context(tpm2dot_gctx->pri_key_obj_hnd));
}

static int
tpm2dot0_create_ch_key(E_TPM2DOT0_PKEY_CTX *tctx, E_TPM2DOT0_RSA_CTX *hptr)
{
	TPM_RC			rc;
	TSS_CONTEXT		*tss_ctx = NULL;
	Create_In		in = { 0 };
	Create_Out		out = { { { 0 } } };
	TPMI_SH_AUTH_SESSION	sess_hnd = TPM_RS_PW;
	const char		*passwd = NULL;
	unsigned int		sess_attr = 0;

	rc = TSS_Create(&tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CREATE_CH_KEY,
		    TPM2DOT0_R_TSS_CREATE_ERROR);
		return (-1);
	}

	OPENSSL_assert(tpm2dot_gctx->pri_key_obj_hnd);
	in.parentHandle = tpm2dot_gctx->pri_key_obj_hnd;

	in.inPublic.t.publicArea.type = TPM_ALG_RSA;
	in.inPublic.t.publicArea.nameAlg = TPM_ALG_SHA256;

	in.inSensitive.t.sensitive.userAuth.t.size = 0;
	in.inSensitive.t.sensitive.data.t.size = 0;

	in.inPublic.t.publicArea.objectAttributes.val = 0;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_FIXEDTPM;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_FIXEDPARENT;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_SENSITIVEDATAORIGIN;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_USERWITHAUTH;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_NODA;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_DECRYPT;
	in.inPublic.t.publicArea.objectAttributes.val |= TPMA_OBJECT_SIGN;

	in.inPublic.t.publicArea.parameters.rsaDetail.symmetric.algorithm = TPM_ALG_NULL;
	in.inPublic.t.publicArea.parameters.rsaDetail.scheme.scheme = TPM_ALG_NULL;
	OPENSSL_assert(tctx->nbits);
	in.inPublic.t.publicArea.parameters.rsaDetail.keyBits = tctx->nbits;
	in.inPublic.t.publicArea.parameters.rsaDetail.exponent = 0;

	in.inPublic.t.publicArea.unique.rsa.t.size = 0;

	in.inPublic.t.publicArea.authPolicy.t.size = 0;

	in.outsideInfo.t.size = 0;

	in.creationPCR.count = 0;

	rc = TSS_Execute(tss_ctx,
	    (RESPONSE_PARAMETERS *)&out, (COMMAND_PARAMETERS *)&in, NULL,
	    TPM_CC_Create, sess_hnd, passwd, sess_attr,
	    TPM_RH_NULL, NULL, 0);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CREATE_CH_KEY,
		    TPM2DOT0_R_TPM__CC__CREATE_ERROR);
		return (-1);
	}

	hptr->ch_key_priv = out.outPrivate;
	hptr->ch_key_pub = out.outPublic;

	rc = TSS_Delete(tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CREATE_CH_KEY,
		    TPM2DOT0_R_TSS_DELETE_ERROR);
		return (-1);
	}

	return (0);
}

static int
tpm2dot0_load_ch_key(E_TPM2DOT0_RSA_CTX *hptr)
{
	TPM_RC			rc;
	TSS_CONTEXT		*tss_ctx = NULL;
	Load_In			in = { 0 };
	Load_Out		out = { 0 };
	TPMI_SH_AUTH_SESSION	sess_hnd = TPM_RS_PW;
	const char		*passwd = NULL;
	unsigned int		sess_attr = 0;

	rc = TSS_Create(&tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_LOAD_CH_KEY,
		    TPM2DOT0_R_TSS_CREATE_ERROR);
		return (-1);
	}

	OPENSSL_assert(tpm2dot_gctx->pri_key_obj_hnd);
	in.parentHandle = tpm2dot_gctx->pri_key_obj_hnd;
	OPENSSL_assert(hptr->ch_key_pub.t.publicArea.type == TPM_ALG_RSA);
	OPENSSL_assert(hptr->ch_key_pub.t.publicArea.parameters.rsaDetail.keyBits);
	in.inPrivate = hptr->ch_key_priv;
	in.inPublic = hptr->ch_key_pub;

	rc = TSS_Execute(tss_ctx,
	    (RESPONSE_PARAMETERS *)&out, (COMMAND_PARAMETERS *)&in, NULL,
	    TPM_CC_Load, sess_hnd, passwd, sess_attr,
	    TPM_RH_NULL, NULL, 0);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_LOAD_CH_KEY,
		    TPM2DOT0_R_TPM__CC__LOAD_ERROR);
		return (-1);
	}

	hptr->ch_key_obj_hnd = out.objectHandle;

	rc = TSS_Delete(tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_LOAD_CH_KEY,
		    TPM2DOT0_R_TSS_DELETE_ERROR);
		return (-1);
	}

	return (0);
}

static int
tpm2dot0_ch_key_decrypt(E_TPM2DOT0_RSA_CTX *hptr,
    unsigned char *to, size_t *tlen, const unsigned char *from, size_t flen)
{
	TPM_RC			rc;
	TSS_CONTEXT		*tss_ctx = NULL;
	RSA_Decrypt_In		in = { 0 };
	RSA_Decrypt_Out		out = { { { 0 } } };
	TPMI_SH_AUTH_SESSION	sess_hnd = TPM_RS_PW;
	const char		*passwd = NULL;
	unsigned int		sess_attr = 0;

	rc = TSS_Create(&tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CH_KEY_DECRYPT,
		    TPM2DOT0_R_TSS_CREATE_ERROR);
		return (-1);
	}

	in.keyHandle = hptr->ch_key_obj_hnd;

	memcpy(in.cipherText.t.buffer, from, flen);
	in.cipherText.t.size = flen;

	in.inScheme.scheme = TPM_ALG_RSAES;
	in.label.t.size = 0;

	rc = TSS_Execute(tss_ctx,
	    (RESPONSE_PARAMETERS *)&out, (COMMAND_PARAMETERS *)&in, NULL,
	    TPM_CC_RSA_Decrypt, sess_hnd, passwd,
	    sess_attr, TPM_RH_NULL, NULL, 0);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CH_KEY_DECRYPT,
		    TPM2DOT0_R_TPM__CC__RSA__DECRYPT_ERROR);
		return (-1);
	}

	memcpy(to, out.message.t.buffer, out.message.t.size);
	*tlen = out.message.t.size;

	rc = TSS_Delete(tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CH_KEY_DECRYPT,
		    TPM2DOT0_R_TSS_DELETE_ERROR);
		return (-1);
	}

	return (0);
}

static int
tpm2dot0_ch_key_sign(E_TPM2DOT0_PKEY_CTX *tctx, E_TPM2DOT0_RSA_CTX *hptr,
    unsigned char *sig, size_t *slen, const unsigned char *from, size_t flen)
{
	TPM_RC			rc;
	TSS_CONTEXT		*tss_ctx = NULL;
	Sign_In			in = { 0 };
	Sign_Out		out = { { 0 } };
	TPMI_SH_AUTH_SESSION	sess_hnd = TPM_RS_PW;
	const char		*passwd = NULL;
	unsigned int		sess_attr = 0;

	rc = TSS_Create(&tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CH_KEY_SING,
		    TPM2DOT0_R_TSS_CREATE_ERROR);
		return (-1);
	}

	in.keyHandle = hptr->ch_key_obj_hnd;

	in.digest.t.size = flen;
	memcpy(in.digest.t.buffer, from, flen);
	in.inScheme.scheme = TPM_ALG_RSASSA;
	switch (EVP_MD_type(tctx->md)) {
	case NID_sha256:
		in.inScheme.details.rsassa.hashAlg = TPM_ALG_SHA256;
		break;
	case NID_sha384:
		in.inScheme.details.rsassa.hashAlg = TPM_ALG_SHA384;
		break;
	default:
		OPENSSL_assert(!EVP_MD_type(tctx->md));
		break;
	}

	in.validation.tag = TPM_ST_HASHCHECK;
	in.validation.hierarchy = TPM_RH_NULL;
	in.validation.digest.t.size = 0;

	rc = TSS_Execute(tss_ctx,
	    (RESPONSE_PARAMETERS *)&out, (COMMAND_PARAMETERS *)&in, NULL,
	    TPM_CC_Sign, sess_hnd, passwd, sess_attr,
	    TPM_RH_NULL, NULL, 0);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CH_KEY_SIGN,
		    TPM2DOT0_R_TPM__CC__SIGN_ERROR);
		return (-1);
	}

	memcpy(sig, out.signature.signature.rsapss.sig.t.buffer, out.signature.signature.rsapss.sig.t.size);
	*slen = out.signature.signature.rsapss.sig.t.size;

	rc = TSS_Delete(tss_ctx);
	if (rc != 0) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_CH_KEY_SIGN,
		    TPM2DOT0_R_TSS_DELETE_ERROR);
		return (-1);
	}

	return (0);
}

static int
tpm2dot0_flush_ch_key(E_TPM2DOT0_RSA_CTX *hptr)
{
	return (tpm2dot0_flush_context(hptr->ch_key_obj_hnd));
}

static int
tpm2dot0_engine_destroy(ENGINE *e)
{
	ERR_unload_TPM2DOT0_strings();
	return (1);
}

static int tpm2dot0_hndidx_rsa = -1;

static int
tpm2dot0_engine_init(ENGINE *e)
{
	if (tpm2dot0_hndidx_rsa == -1) {
		tpm2dot0_hndidx_rsa = RSA_get_ex_new_index(0, "TPM2.0 RSA key handle", NULL, NULL, NULL);
	}

	if (tpm2dot_gctx == NULL) {
		if (pthread_mutex_init(&e_tpm_mutex, NULL) != 0) {
			return(0);
		}
		if (tpm2dot0_startup() != 0) {
			return (0);
		}

		if (tpm2dot0_flush_all_handles() != 0) {
			return (0);
		}

		tpm2dot_gctx = OPENSSL_malloc(sizeof (E_TPM2DOT0_GL_CTX));

		if (tpm2dot0_create_pri_ek() != 0) {
			return (0);
		}
	}

	return (1);
}

static int
tpm2dot0_engine_finish(ENGINE *e)
{
	if (tpm2dot_gctx == NULL) {
		return (1);
	}

	if (tpm2dot0_flush_pri_ek() != 0) {
		return (0);
	}

	OPENSSL_free(tpm2dot_gctx);
	tpm2dot_gctx = NULL;

	return (1);
}

static EVP_PKEY *
tpm2dot0_engine_load_privkey(ENGINE *e, const char *key_id,
    UI_METHOD *ui_method, void *callback_data)
{
	BIO		*in;
	EVP_PKEY	*pkey;

	if (!(in = BIO_new_file(key_id, "r"))) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_ENGINE_LOAD_PRIVKEY,
		    TPM2DOT0_R_BIO_ERROR);
		return (NULL);
	}

	pkey = PEM_read_bio_PrivateKey(in, NULL, NULL, NULL);

	BIO_free(in);

	return (pkey);
}

static int
tpm2dot0_pmeth_init(EVP_PKEY_CTX *ctx)
{
	E_TPM2DOT0_PKEY_CTX	*tctx;

	tctx = OPENSSL_malloc(sizeof (E_TPM2DOT0_PKEY_CTX));
	tctx->nbits = 2048;
	tctx->pad_mode = RSA_PKCS1_PADDING;
	tctx->md = NULL;
	EVP_PKEY_CTX_set_data(ctx, tctx);

	return (1);
}

static int
tpm2dot0_pmeth_copy(EVP_PKEY_CTX *dst, EVP_PKEY_CTX *src)
{
	E_TPM2DOT0_PKEY_CTX	*tdctx, *tsctx;

	tsctx = EVP_PKEY_CTX_get_data(src);

	tdctx = OPENSSL_malloc(sizeof (E_TPM2DOT0_PKEY_CTX));
	if (!tdctx) {
		return (0);
	}
	EVP_PKEY_CTX_set_data(dst, tdctx);

	*tdctx = *tsctx;

	return (1);
}

static void
tpm2dot0_pmeth_cleanup(EVP_PKEY_CTX *ctx)
{
	E_TPM2DOT0_PKEY_CTX	*tctx;

	tctx = EVP_PKEY_CTX_get_data(ctx);
	OPENSSL_free(tctx);
}

static int
tpm2dot0_pmeth_ctrl(EVP_PKEY_CTX *ctx, int type, int p1, void *p2)
{
	E_TPM2DOT0_PKEY_CTX	*tctx;

	tctx = EVP_PKEY_CTX_get_data(ctx);

	switch (type) {
	case EVP_PKEY_CTRL_MD:
		if (tctx->pad_mode != RSA_PKCS1_PADDING) {
			TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_PMETH_CTRL,
			    TPM2DOT0_R_INVALID_PADDING_TYPE);
			return (0);
		}
		tctx->md = p2;
		return (1);
	case EVP_PKEY_CTRL_DIGESTINIT:
		return (1);
	case EVP_PKEY_CTRL_RSA_KEYGEN_BITS:
		tctx->nbits = p1;
		return (1);
	case EVP_PKEY_CTRL_GET_RSA_PADDING:
		*(int *)p2 = tctx->pad_mode;
		return (1);
	default:
		break;
	}

	return (-2);
}

static int
tpm2dot0_pmeth_ctrl_str(EVP_PKEY_CTX *ctx, const char *type, const char *value)
{
	if (strcmp(type, "rsa_padding_mode") == 0) {
		int	pm;

		if (strcmp(value, "pkcs1") == 0)
			pm = RSA_PKCS1_PADDING;
		else if (strcmp(value, "none") == 0)
			pm = RSA_NO_PADDING;
		else if (strcmp(value, "oeap") == 0)
			pm = RSA_PKCS1_OAEP_PADDING;
		else if (strcmp(value, "oaep") == 0)
			pm = RSA_PKCS1_OAEP_PADDING;
		else if (strcmp(value, "pss") == 0)
			pm = RSA_PKCS1_PSS_PADDING;
		else {
			TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_PMETH_CTRL_STR,
			    TPM2DOT0_R_UNKNOWN_PADDING_TYPE);
			return (-1);
		}
		return (EVP_PKEY_CTX_set_rsa_padding(ctx, pm));
	}
	if (strcmp(type, "rsa_keygen_bits") == 0) {
		int	nbits;
		nbits = atoi(value);
		return (EVP_PKEY_CTX_set_rsa_keygen_bits(ctx, nbits));
	}

	return (-1);
}

static int
tpm2dot0_pmeth_keygen(EVP_PKEY_CTX *ctx, EVP_PKEY *pkey)
{
	E_TPM2DOT0_PKEY_CTX	*tctx;
	E_TPM2DOT0_RSA_CTX	*hptr;
	RSA			*rsa;
	int			ret = 1;


	tctx = EVP_PKEY_CTX_get_data(ctx);

	hptr = OPENSSL_malloc(sizeof (E_TPM2DOT0_RSA_CTX));
	if (!hptr) {
		return (0);
	}
	pthread_mutex_lock(&e_tpm_mutex);
	if (tpm2dot0_create_ch_key(tctx, hptr) != 0) {
		ret = 0;
		goto cleanup;
	}
	if (tpm2dot0_load_ch_key(hptr) != 0) {
		ret = 0;
		goto cleanup;
	}

	rsa = RSA_new_method(pkey->engine);
	RSA_set_ex_data(rsa, tpm2dot0_hndidx_rsa, hptr);

	rsa->n = BN_new();
	if (!rsa->n) {
		ret = 0;
		goto cleanup;
	}
	if (!BN_bin2bn(hptr->ch_key_pub.t.publicArea.unique.rsa.t.buffer,
	    hptr->ch_key_pub.t.publicArea.unique.rsa.t.size, rsa->n)) {
		ret = 0;
		goto cleanup;
	}

	rsa->e = BN_new();
	if (!rsa->e) {
		ret = 0;
		goto cleanup;
	}
	if (!BN_set_word(rsa->e, 65537)) {
		ret = 0;
		goto cleanup;
	}

	rsa->d = NULL;

	EVP_PKEY_assign_RSA(pkey, rsa);

	if (tpm2dot0_flush_ch_key(hptr) != 0) {
		ret = 0;
		goto cleanup;
	}
cleanup:
	pthread_mutex_unlock(&e_tpm_mutex);
	return (ret);
}

static int
tpm2dot0_pmeth_sign(EVP_PKEY_CTX *ctx, unsigned char *sig, size_t *siglen,
    const unsigned char *tbs, size_t tbslen)
{
	EVP_PKEY		*pkey;
	E_TPM2DOT0_PKEY_CTX	*tctx;
	RSA			*rsa;
	E_TPM2DOT0_RSA_CTX	*hptr;
	int			ret = 1;

	pkey = EVP_PKEY_CTX_get0_pkey(ctx);
	tctx = EVP_PKEY_CTX_get_data(ctx);
	rsa = EVP_PKEY_get1_RSA(pkey);
	hptr = RSA_get_ex_data(rsa, tpm2dot0_hndidx_rsa);
	if (hptr == NULL) {
		/*
		 * non-TPM-based RSA key
		 */
		unsigned int len;
		ret = (RSA_sign(EVP_MD_type(tctx->md), tbs, tbslen,
		    sig, &len, rsa));
		*siglen = len;
		return (ret);
	}

	pthread_mutex_lock(&e_tpm_mutex);
	if (tpm2dot0_load_ch_key(hptr) != 0) {
		ret = 0;
		goto cleanup;
	}

	if (tpm2dot0_ch_key_sign(tctx, hptr, sig, siglen,
	    tbs, tbslen) != 0) {
		ret = 0;
		goto cleanup;
	}

	if (tpm2dot0_flush_ch_key(hptr) != 0) {
		ret = 0;
		goto cleanup;
	}
cleanup:
	pthread_mutex_unlock(&e_tpm_mutex);
	return (ret);
}

static int
tpm2dot0_pmeth_verify(EVP_PKEY_CTX *ctx, const unsigned char *sig,
    size_t siglen, const unsigned char *tbs, size_t tbslen)
{
	EVP_PKEY		*pkey;
	E_TPM2DOT0_PKEY_CTX	*tctx;
	RSA			*rsa;
	int			ret;

	pkey = EVP_PKEY_CTX_get0_pkey(ctx);
	tctx = EVP_PKEY_CTX_get_data(ctx);
	rsa = EVP_PKEY_get1_RSA(pkey);

	ret = RSA_verify(EVP_MD_type(tctx->md), tbs, tbslen, sig, siglen, rsa);

	RSA_free(rsa);

	return (ret);
}

static int
tpm2dot0_pmeth_encrypt(EVP_PKEY_CTX *ctx, unsigned char *out, size_t *outlen,
    const unsigned char *in, size_t inlen)
{
	EVP_PKEY		*pkey;
	E_TPM2DOT0_PKEY_CTX	*tctx;
	RSA			*rsa;
	E_TPM2DOT0_RSA_CTX	*hptr;
	unsigned char		*tmp_out;
	int			ret = 1;

	pkey = EVP_PKEY_CTX_get0_pkey(ctx);
	tctx = EVP_PKEY_CTX_get_data(ctx);
	rsa = EVP_PKEY_get1_RSA(pkey);
	hptr = RSA_get_ex_data(rsa, tpm2dot0_hndidx_rsa);

	tmp_out = out;
	if (!out) {
		tmp_out = OPENSSL_malloc(hptr->ch_key_pub.t.publicArea.parameters.rsaDetail.keyBits / 8);
	}

	*outlen = RSA_public_encrypt(inlen, in, tmp_out, rsa, tctx->pad_mode);
	if (*outlen <= 0) {
		ret = -1;
	}

	if (!out) {
		OPENSSL_free(tmp_out);
	}

	RSA_free(rsa);

	return (ret);
}

static int
tpm2dot0_pmeth_decrypt(EVP_PKEY_CTX *ctx, unsigned char *out, size_t *outlen,
    const unsigned char *in, size_t inlen)
{
	EVP_PKEY		*pkey;
	RSA			*rsa;
	E_TPM2DOT0_RSA_CTX	*hptr;
	int			ret = 1;

	pkey = EVP_PKEY_CTX_get0_pkey(ctx);
	rsa = EVP_PKEY_get1_RSA(pkey);
	hptr = RSA_get_ex_data(rsa, tpm2dot0_hndidx_rsa);

	pthread_mutex_lock(&e_tpm_mutex);
	if (tpm2dot0_load_ch_key(hptr) != 0) {
		ret = 0;
		goto cleanup;
	}

	if (!out) {
		unsigned char	*tmp_out;
		tmp_out = OPENSSL_malloc(hptr->ch_key_pub.t.publicArea.parameters.rsaDetail.keyBits / 8);
		if (tpm2dot0_ch_key_decrypt(hptr, tmp_out, outlen, in, inlen) != 0) {
			ret = 0;
			goto cleanup;
		}
		OPENSSL_free(tmp_out);
	} else {
		if (tpm2dot0_ch_key_decrypt(hptr, out, outlen, in, inlen) != 0) {
			ret = 0;
			goto cleanup;
		}
	}

	if (tpm2dot0_flush_ch_key(hptr) != 0) {
		ret = 0;
		goto cleanup;
	}
cleanup:
	pthread_mutex_unlock(&e_tpm_mutex);
	return (ret);
}

const EVP_PKEY_ASN1_METHOD	*generic_ameth_rsa;

static int
tpm2dot0_pub_decode(EVP_PKEY *pkey, X509_PUBKEY *pubkey)
{
	const unsigned char	*p;
	int			plen;
	RSA			*rsa = NULL;

	if (!X509_PUBKEY_get0_param(NULL, &p, &plen, NULL, pubkey)) {
		return (0);
	}

	if (!(rsa = d2i_RSAPublicKey(NULL, &p, plen))) {
		return (0);
	}

	EVP_PKEY_assign_RSA(pkey, rsa);

	return (1);
}

static int
tpm2dot0_pub_encode(X509_PUBKEY *pub, const EVP_PKEY *pkey)
{
	unsigned char	*p = NULL;
	int		 plen;

	plen = i2d_RSAPublicKey(pkey->pkey.rsa, &p);
	if (plen <= 0) {
		return (0);
	}

	if (X509_PUBKEY_set0_param(pub, OBJ_nid2obj(EVP_PKEY_RSA),
	    V_ASN1_NULL, NULL, p, plen)) {
		return (1);
	}

	OPENSSL_free(p);

	return (0);
}

static int
tpm2dot0_pub_cmp(const EVP_PKEY *a, const EVP_PKEY *b)
{
	if (BN_cmp(b->pkey.rsa->n, a->pkey.rsa->n) != 0 ||
	    BN_cmp(b->pkey.rsa->e, a->pkey.rsa->e) != 0) {
		return (0);
	}

	return (1);
}

static int
tpm2dot0_pub_print(BIO *out, const EVP_PKEY *pkey, int indent, ASN1_PCTX *pctx)
{
	return (0);
}

static int
tpm2dot0_pkey_size(const EVP_PKEY *pkey)
{
	return (RSA_size(pkey->pkey.rsa));
}

static int
tpm2dot0_pkey_bits(const EVP_PKEY *pkey)
{
	return (BN_num_bits(pkey->pkey.rsa->n));
}

typedef struct {
	ASN1_OCTET_STRING	*encrypted_priv_key;
	ASN1_OCTET_STRING	*public_key;
} TPM_KEY_INFO;

ASN1_SEQUENCE(TPM_KEY_INFO) = {
	ASN1_SIMPLE(TPM_KEY_INFO, encrypted_priv_key, ASN1_OCTET_STRING),
	ASN1_SIMPLE(TPM_KEY_INFO, public_key, ASN1_OCTET_STRING),
} ASN1_SEQUENCE_END(TPM_KEY_INFO)
IMPLEMENT_ASN1_FUNCTIONS(TPM_KEY_INFO)

static int
tpm2dot0_priv_decode(EVP_PKEY *pkey, PKCS8_PRIV_KEY_INFO *p8info)
{
	E_TPM2DOT0_RSA_CTX	*hptr;
	RSA			*rsa;
	const unsigned char	*p = NULL;
	int			plen = 0;
	TPM_KEY_INFO		*tki;
	int			ret = 1;

	hptr = OPENSSL_malloc(sizeof (E_TPM2DOT0_RSA_CTX));
	if (!hptr) {
		return (0);
	}

	if (!PKCS8_pkey_get0(NULL, &p, &plen, NULL, p8info)) {
		return (0);
	}

	if (!(tki = d2i_TPM_KEY_INFO(NULL, &p, plen))) {
		TPM2DOT0err(TPM2DOT0_F_TPM2DOT0_PRIV_DECODE,
		    TPM2DOT0_R_PARSING_TPM_KEY_INFO);
		return (0);
	}

	memcpy(&hptr->ch_key_priv, ASN1_STRING_data(tki->encrypted_priv_key), ASN1_STRING_length(tki->encrypted_priv_key));
	memcpy(&hptr->ch_key_pub, ASN1_STRING_data(tki->public_key), ASN1_STRING_length(tki->public_key));

	pthread_mutex_lock(&e_tpm_mutex);
	TPM_KEY_INFO_free(tki);
	
	if (tpm2dot0_load_ch_key(hptr) != 0) {
		ret = 0;
		goto cleanup;
	}

	rsa = RSA_new_method(pkey->engine);
	RSA_set_ex_data(rsa, tpm2dot0_hndidx_rsa, hptr);

	rsa->n = BN_new();
	if (!rsa->n) {
		ret = 0;
		goto cleanup;
	}

	if (!BN_bin2bn(hptr->ch_key_pub.t.publicArea.unique.rsa.t.buffer, hptr->ch_key_pub.t.publicArea.unique.rsa.t.size, rsa->n)) {
		ret = 0;
		goto cleanup;
	}

	rsa->e = BN_new();
	if (!rsa->e) {
		ret = 0;
		goto cleanup;
	}
	if (!BN_set_word(rsa->e, 65537)) {
		ret = 0;
		goto cleanup;
	}

	rsa->d = NULL;

	EVP_PKEY_assign_RSA(pkey, rsa);

	if (tpm2dot0_flush_ch_key(hptr) != 0) {
		ret = 0;
		goto cleanup;
	}
cleanup:
	pthread_mutex_unlock(&e_tpm_mutex);
	return (ret);
}

static int
tpm2dot0_priv_decode_rsa(EVP_PKEY *pkey, PKCS8_PRIV_KEY_INFO *p8inf)
{
	const unsigned char	*p = NULL;
	int			plen = 0;
	RSA			*rsa;

	if (!PKCS8_pkey_get0(NULL, &p, &plen, NULL, p8inf)) {
		return (0);
	}

	if (!(rsa = d2i_RSAPrivateKey(NULL, &p, plen))) {
		return (0);
	}
	EVP_PKEY_assign_RSA(pkey, rsa);

	return (1);
}

static int
tpm2dot0_priv_encode_rsa(PKCS8_PRIV_KEY_INFO *p8info, const EVP_PKEY *pkey)
{
	E_TPM2DOT0_RSA_CTX	*hptr;
	TPM_KEY_INFO		*tki;
	unsigned char		*p = NULL;
	int			plen;

	hptr = RSA_get_ex_data(pkey->pkey.rsa, tpm2dot0_hndidx_rsa);
	if (hptr == NULL) {
		/*
		 * non-TPM-based RSA key
		 */
		plen = i2d_RSAPrivateKey(pkey->pkey.rsa, &p);
		if (plen <= 0) {
			return (0);
		}

		if (!PKCS8_pkey_set0(p8info, OBJ_nid2obj(NID_rsaEncryption), 0,
		    V_ASN1_NULL, NULL, p, plen)) {
			return (0);
		}

		return (1);
	}

	tki = TPM_KEY_INFO_new();
	if (!tki) {
		return (0);
	}
	tki->encrypted_priv_key = ASN1_OCTET_STRING_new();
	if (!ASN1_OCTET_STRING_set(tki->encrypted_priv_key, (const unsigned char *)&hptr->ch_key_priv, sizeof (hptr->ch_key_priv))) {
		return (0);
	}
	tki->public_key = ASN1_OCTET_STRING_new();
	if (!ASN1_OCTET_STRING_set(tki->public_key, (const unsigned char *)&hptr->ch_key_pub, sizeof (hptr->ch_key_pub))) {
		return (0);
	}

	plen = i2d_TPM_KEY_INFO(tki, &p);
	if (plen <= 0) {
		return (0);
	}

	if (PKCS8_pkey_set0(p8info, OBJ_nid2obj(NID_Private), 0,
			    V_ASN1_NULL, NULL, p, plen)) {
		return (1);
	}

	OPENSSL_free(p);
	return (0);
}

static int
tpm2dot0_priv_print_rsa(BIO *out, const EVP_PKEY *pkey, int indent,
    ASN1_PCTX *pctx)
{
	return (0);
}

static int
tpm2dot0_pkey_ctrl(EVP_PKEY *pkey, int op, long arg1, void *arg2)
{
	switch (op) {
	case ASN1_PKEY_CTRL_DEFAULT_MD_NID:
		*(int *)arg2 = NID_sha256WithRSAEncryption;
		return (1);
	default:
		break;
	}

	return (-2);
}

static void
tpm2dot0_pkey_free(EVP_PKEY *pkey)
{
	E_TPM2DOT0_RSA_CTX	*hptr;

	if (pkey->pkey.rsa) {
		hptr = RSA_get_ex_data(pkey->pkey.rsa, tpm2dot0_hndidx_rsa);
		RSA_free(pkey->pkey.rsa);
		if (!hptr) {
			return;
		}
		OPENSSL_free(hptr);
	}
}

static int tpm2dot0_pmeth_nids[] = {
	NID_rsaEncryption
};
static EVP_PKEY_METHOD *tpm2dot0_pmeth;

static int
tpm2dot0_engine_pkey_meths(ENGINE *e, EVP_PKEY_METHOD **pmeth,
    const int **nids, int nid)
{
	if (!pmeth) {
		*nids = tpm2dot0_pmeth_nids;
		return (1);
	}

	switch (nid) {
	case NID_rsaEncryption:
		*pmeth = tpm2dot0_pmeth;
		return (1);
	default:
		break;
	}

	return (0);
}

static int tpm2dot0_ameth_nids[] = {
	NID_rsaEncryption, NID_Private
};
static EVP_PKEY_ASN1_METHOD *tpm2dot0_ameth_rsa;
static EVP_PKEY_ASN1_METHOD *tpm2dot0_ameth_private;

static int
tpm2dot0_engine_pkey_asn1_meths(ENGINE *e, EVP_PKEY_ASN1_METHOD **ameth,
				const int **nids, int nid)
{
	if (!ameth) {
		*nids = tpm2dot0_ameth_nids;
		return (sizeof (tpm2dot0_ameth_nids) / sizeof (int));
	}

	switch (nid) {
	case NID_rsaEncryption:
		*ameth = tpm2dot0_ameth_rsa;
		return (1);
	case NID_Private:
		*ameth = tpm2dot0_ameth_private;
		return (1);
	default:
		break;
	}

	return (0);
}

const RSA_METHOD	*generic_rsa_method;

static int
tpm2dot0_rsa_pub_decrypt(int flen, const unsigned char *from,
    unsigned char *to, RSA *rsa, int padding)
{
	return (generic_rsa_method->rsa_pub_dec(flen, from, to, rsa, padding));
}

static int
tpm2dot0_rsa_priv_decrypt(int flen, const unsigned char *from,
    unsigned char *to, RSA *rsa, int padding)
{
	E_TPM2DOT0_RSA_CTX	*hptr;
	size_t			tlen;
	int			ret = 1;

	if (padding != RSA_PKCS1_PADDING) {
		return (-1);
	}

	hptr = RSA_get_ex_data(rsa, tpm2dot0_hndidx_rsa);

	pthread_mutex_lock(&e_tpm_mutex);
	if (tpm2dot0_load_ch_key(hptr) != 0) {
		ret = -1;
		goto cleanup;
	}

	if (tpm2dot0_ch_key_decrypt(hptr, to, &tlen, from, flen) != 0) {
		ret = -1;
		goto cleanup;
	}

	if (tpm2dot0_flush_ch_key(hptr) != 0) {
		ret = -1;
		goto cleanup;
	}
cleanup:
	pthread_mutex_unlock(&e_tpm_mutex);
	if (ret == -1)
		return(ret);

	return (tlen);
}

static int
tpm2dot0_bn_mod_exp(BIGNUM *r, const BIGNUM *a, const BIGNUM *p,
    const BIGNUM *m, BN_CTX *ctx, BN_MONT_CTX *m_ctx)
{
	return (generic_rsa_method->bn_mod_exp(r, a, p, m, ctx, m_ctx));
}

static int
tpm2dot0_rsa_init(RSA *rsa)
{
	return (generic_rsa_method->init(rsa));
}

static int
tpm2dot0_rsa_finish(RSA *rsa)
{
	return (generic_rsa_method->finish(rsa));
}

static RSA_METHOD	tpm2dot0_rsa_method = {
	"TPM2.0 RSA method",
	NULL,			/* rsa_pub_encrypt */
	tpm2dot0_rsa_pub_decrypt,
	NULL,			/* rsa_priv_encrypt */
	tpm2dot0_rsa_priv_decrypt,
	NULL,			/* rsa_mod_exp */
	tpm2dot0_bn_mod_exp,
	tpm2dot0_rsa_init,
	tpm2dot0_rsa_finish,
	RSA_FLAG_EXT_PKEY,
	NULL,			/* app_data */
	NULL,			/* rsa_sign */
	NULL,			/* rsa_verify */
	NULL			/* rsa_keygen */
};

static int
bind_helper(ENGINE *e)
{
	ERR_load_TPM2DOT0_strings();

	tpm2dot0_pmeth = EVP_PKEY_meth_new(NID_rsaEncryption, 0);
	EVP_PKEY_meth_set_init(tpm2dot0_pmeth, tpm2dot0_pmeth_init);
	EVP_PKEY_meth_set_copy(tpm2dot0_pmeth, tpm2dot0_pmeth_copy);
	EVP_PKEY_meth_set_cleanup(tpm2dot0_pmeth, tpm2dot0_pmeth_cleanup);
	EVP_PKEY_meth_set_ctrl(tpm2dot0_pmeth, tpm2dot0_pmeth_ctrl, tpm2dot0_pmeth_ctrl_str);
	EVP_PKEY_meth_set_keygen(tpm2dot0_pmeth, NULL, tpm2dot0_pmeth_keygen);
	EVP_PKEY_meth_set_sign(tpm2dot0_pmeth, NULL, tpm2dot0_pmeth_sign);
	EVP_PKEY_meth_set_verify(tpm2dot0_pmeth, NULL, tpm2dot0_pmeth_verify);
	EVP_PKEY_meth_set_encrypt(tpm2dot0_pmeth, NULL, tpm2dot0_pmeth_encrypt);
	EVP_PKEY_meth_set_decrypt(tpm2dot0_pmeth, NULL, tpm2dot0_pmeth_decrypt);

	generic_ameth_rsa = EVP_PKEY_asn1_find(NULL, NID_rsaEncryption);
	tpm2dot0_ameth_rsa = EVP_PKEY_asn1_new(NID_rsaEncryption, 0, "Private", "Private");
	EVP_PKEY_asn1_copy(tpm2dot0_ameth_rsa, generic_ameth_rsa);
	tpm2dot0_ameth_private = EVP_PKEY_asn1_new(NID_Private, 0, "Private", "Private");
	EVP_PKEY_asn1_set_public(tpm2dot0_ameth_rsa, tpm2dot0_pub_decode, tpm2dot0_pub_encode, tpm2dot0_pub_cmp, tpm2dot0_pub_print, tpm2dot0_pkey_size, tpm2dot0_pkey_bits);
	EVP_PKEY_asn1_set_private(tpm2dot0_ameth_rsa, tpm2dot0_priv_decode_rsa, tpm2dot0_priv_encode_rsa, tpm2dot0_priv_print_rsa);
	EVP_PKEY_asn1_set_private(tpm2dot0_ameth_private, tpm2dot0_priv_decode, NULL, NULL);
	EVP_PKEY_asn1_set_ctrl(tpm2dot0_ameth_rsa, tpm2dot0_pkey_ctrl);
	EVP_PKEY_asn1_set_free(tpm2dot0_ameth_rsa, tpm2dot0_pkey_free);
	EVP_PKEY_asn1_set_free(tpm2dot0_ameth_private, tpm2dot0_pkey_free);

	if (!ENGINE_set_destroy_function(e, tpm2dot0_engine_destroy) ||
	    !ENGINE_set_init_function(e, tpm2dot0_engine_init) ||
	    !ENGINE_set_finish_function(e, tpm2dot0_engine_finish) ||
	    !ENGINE_set_pkey_meths(e, tpm2dot0_engine_pkey_meths) ||
	    !ENGINE_set_pkey_asn1_meths(e, tpm2dot0_engine_pkey_asn1_meths) ||
	    !ENGINE_set_load_privkey_function(e,
	    tpm2dot0_engine_load_privkey)) {
		return (0);
	}

	generic_rsa_method = RSA_get_default_method();
	if (!ENGINE_set_RSA(e, &tpm2dot0_rsa_method)) {
		return (0);
	}

	if (!ENGINE_register_pkey_asn1_meths(e)) {
		return (0);
	}

	return (1);
}

static int
bind_fn(ENGINE *e, const char *id)
{
	int ret = 0;

	if (id && strcmp(id, engine_id)) {
		goto end;
	}

	if (!ENGINE_set_id(e, engine_id)) {
		goto end;
	}
	if (!ENGINE_set_name(e, engine_name)) {
		goto end;
	}

	if (!bind_helper(e)) {
		goto end;
	}

	ret = 1;
end:
	return (ret);
}

IMPLEMENT_DYNAMIC_BIND_FN(bind_fn)
IMPLEMENT_DYNAMIC_CHECK_FN()
