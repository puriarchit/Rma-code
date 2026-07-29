import zipfile
import os

zip_path = r"D:\LexisNexis\MWV01TF_WorldCompliancePlus_20260508_075958.zip"
output_file = r"D:\LexisNexis\max_lengths.txt"

print("Opening ZIP file directly (No extraction needed)...\n")
out_lines = []

with zipfile.ZipFile(zip_path, "r") as z:
    for name in z.namelist():
        if name.endswith(".txt"):
            filename = os.path.basename(name)
            print(f"🔍 Scanning file inside ZIP: {filename} ... Please wait...")
            out_lines.append(f"File: {filename}\n")
            
            try:
                with z.open(name, "r") as f:
                    # Clean carriage returns and split by pipe
                    header_line = f.readline().decode("utf-8", errors="ignore")
                    header = header_line.strip('\r\n').split('|')



                    File: AssociatedEntity.txt
  - EntityGUID: Max Length = 36
  - AssociatedEntityGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 17
  - LastUpdated: Max Length = 23
  - Source Name: Max Length = 161
--------------------------------------------------
File: ConsolidatedSanction.txt
  - ConsolidatedSanctionGUID: Max Length = 36
  - EntityGUID: Max Length = 36
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: Entity.txt
  - EntityGUID: Max Length = 36
  - EntityTypeDesc: Max Length = 12
  - Gender: Max Length = 14
  - Name: Max Length = 255
  - FirstName: Max Length = 52
  - MiddleName: Max Length = 76
  - LastName: Max Length = 255
  - Prefix: Max Length = 30
  - Suffix: Max Length = 10
  - Title: Max Length = 226
  - IsDeceased: Max Length = 1
  - DeceasedYear: Max Length = 4
  - DeceasedMonth: Max Length = 2
  - DeceasedDay: Max Length = 2
  - IsRelatedEntity: Max Length = 1
  - EntityID: Max Length = 8
  - LookupID: Max Length = 36
  - LastUpdated: Max Length = 23
  - AssociatedPhoto: Max Length = 1
--------------------------------------------------
File: EntityAddress.txt
  - EntityGUID: Max Length = 36
  - EntityAddressGUID: Max Length = 36
  - AddressTypeDesc: Max Length = 21
  - Address1: Max Length = 254
  - Address2: Max Length = 255
  - City: Max Length = 50
  - StateProvinceRegion: Max Length = 50
  - PostalCode: Max Length = 15
  - Country: Max Length = 48
  - ISOStandard: Max Length = 4
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityAdverseMedia.txt
  - EntityGUID: Max Length = 36
  - EntityAdverseMediaGUID: Max Length = 36
  - AdverseMediaDesc: Max Length = 8
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityAdverseMediaSubCategory.txt
  - EntityAdverseMediaGUID: Max Length = 36
  - EntityAdverseMediaSubCategoryGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 20
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityAlias.txt
  - EntityGUID: Max Length = 36
  - EntityAliasGUID: Max Length = 36
  - AliasTypeDesc: Max Length = 29
  - EnglishDescription: Max Length = 22
  - Name: Max Length = 254
  - FirstName: Max Length = 65
  - MiddleName: Max Length = 76
  - LastName: Max Length = 255
  - Prefix: Max Length = 30
  - Suffix: Max Length = 10
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityCountryAssociation.txt
  - EntityGUID: Max Length = 36
  - EntityCountryAssociationGUID: Max Length = 36
  - AssociationTypeDesc: Max Length = 20
  - AdministrativeUnitName: Max Length = 48
  - ISOStandard: Max Length = 4
  - OwnershipPercentageCalc: Max Length = 6
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityDeletes.txt
  - EntityGUID: Max Length = 0
  - DateDeleted: Max Length = 0
--------------------------------------------------
File: EntityDOB.txt
  - EntityGUID: Max Length = 36
  - EntityDOBGUID: Max Length = 36
  - BirthYear: Max Length = 4
  - BirthMonth: Max Length = 2
  - BirthDay: Max Length = 2
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityEnforcement.txt
  - EntityGUID: Max Length = 36
  - EntityEnforcementGUID: Max Length = 36
  - EnforcementDesc: Max Length = 8
  - SourceName: Max Length = 144
  - SourceNameAbbrev: Max Length = 10
  - AdministrativeUnitName: Max Length = 48
  - ISOStandard: Max Length = 3
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityEnforcementSubCategory.txt
  - EntityEnforcementGUID: Max Length = 36
  - EntityEnforcementSubCategoryGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 20
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityIdentification.txt
  - EntityGUID: Max Length = 36
  - EntityIdentificationGUID: Max Length = 36
  - AdministrativeUnitName: Max Length = 48
  - ISOStandard: Max Length = 4
  - IdentificationIssuer: Max Length = 245
  - IdentificationTypeDesc: Max Length = 83
  - IdentificationNumber: Max Length = 99
  - IssueYear: Max Length = 4
  - IssueMonth: Max Length = 2
  - IssueDay: Max Length = 2
  - ExpirationYear: Max Length = 4
  - ExpirationMonth: Max Length = 2
  - ExpirationDay: Max Length = 2
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityPEP.txt
  - EntityGUID: Max Length = 36
  - EntityPEPGUID: Max Length = 36
  - IsPrimaryPEP: Max Length = 1
  - IsActivePEP: Max Length = 1
  - IsInCountryPEPOnly: Max Length = 1
  - PEPAdminLevelDesc: Max Length = 15
  - ISOAdministrativeUnitLevel0: Max Length = 3
  - AdministrativeUnitLevel0: Max Length = 48
  - AdministrativeUnitLevel1: Max Length = 56
  - AdministrativeUnitLevel2: Max Length = 49
  - AdministrativeUnitLevel3: Max Length = 43
  - AdministrativeUnitLevel4: Max Length = 48
  - GoverningInstitution: Max Length = 100
  - GoverningRole: Max Length = 100
  - EffectiveYear: Max Length = 4
  - EffectiveMonth: Max Length = 2
  - EffectiveDay: Max Length = 2
  - EffectiveDateTypeDesc: Max Length = 9
  - ExpirationYear: Max Length = 4
  - ExpirationMonth: Max Length = 2
  - ExpirationDay: Max Length = 2
  - ExpirationDateTypeDesc: Max Length = 8
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityPEPSubCategory.txt
  - EntityPEPGUID: Max Length = 36
  - EntityPEPSubCategoryGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 13
  - SubCategoryDesc: Max Length = 22
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityPosition.txt
  - EntityGUID: Max Length = 36
  - EntityPositionGUID: Max Length = 36
  - Position: Max Length = 500
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityRelationship.txt
  - ParentEntityGUID: Max Length = 36
  - RelatedEntityGUID: Max Length = 36
  - EntityRelationshipGUID: Max Length = 36
  - GroupDesc: Max Length = 12
  - RelationshipDesc: Max Length = 24
  - OwnershipPercentage: Max Length = 6
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntityRemark.txt
  - EntityGUID: Max Length = 36
  - EntityRemarkGUID: Max Length = 36
  - Remark: Max Length = 566348
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntitySanction.txt
  - EntityGUID: Max Length = 36
  - EntitySanctionGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 13
  - ConsolidatedSanctionGUID: Max Length = 36
  - SourceName: Max Length = 161
  - SourceNameAbbrev: Max Length = 10
  - AdministrativeUnitName: Max Length = 48
  - ISOStandard: Max Length = 3
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntitySanctionDesignation.txt
  - EntitySanctionGUID: Max Length = 36
  - EntitySanctionDesignationGUID: Max Length = 36
  - DesignationName: Max Length = 9
  - SubDesignationName: Max Length = 13
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntitySOE.txt
  - EntityGUID: Max Length = 36
  - EntitySOEGUID: Max Length = 36
  - IsActive: Max Length = 1
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntitySOEDomain.txt
  - EntitySOEGUID: Max Length = 36
  - EntitySOEDomainGUID: Max Length = 36
  - SOEDomainDesc: Max Length = 20
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntitySOESubCategory.txt
  - EntitySOEGUID: Max Length = 36
  - EntitySOESubCategoryGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 17
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: EntitySourceItem.txt
  - EntityGUID: Max Length = 36
  - EntitySourceItemGUID: Max Length = 36
  - SourceURI: Max Length = 2859
  - LastUpdated: Max Length = 23
--------------------------------------------------
File: FATCARegInst.txt
  - EntityGUID: Max Length = 0
  - FATCARegInstGUID: Max Length = 0
  - SubCategoryLabel: Max Length = 0
  - LastUpdated: Max Length = 0
  - Source Name: Max Length = 0
--------------------------------------------------
File: IHSOFACVessels.txt
  - EntityGUID: Max Length = 36
  - IHSOFACVesselsGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 16
  - LastUpdated: Max Length = 23
  - Vessel Type: Max Length = 40
  - Gross Tonnage: Max Length = 6
  - Country of Build: Max Length = 28
  - Year of Build: Max Length = 4
  - Yard Number: Max Length = 12
  - Ship Status: Max Length = 29
  - Deadweight: Max Length = 6
  - Port of Registry: Max Length = 27
  - Source Name: Max Length = 36
  - ExName: Max Length = 25
  - FlagEffectiveDate: Max Length = 8
  - ShipStatusEffectiveDate: Max Length = 8
  - GroupBeneficialOwner: Max Length = 30
  - GroupBeneficialOwnerCompanyCode: Max Length = 7
  - GroupBeneficialOwnerCountryOfControl: Max Length = 27
  - GroupBeneficialOwnerCountryofDomicile: Max Length = 27
  - Operator: Max Length = 30
  - OperatorCompanyCode: Max Length = 7
  - OperatorCountryOfControl: Max Length = 27
  - OperatorCountryofDomicileName: Max Length = 27
  - OperatorCountryOfRegistration: Max Length = 27
  - RegisteredOwner: Max Length = 30
  - RegisteredOwnerCode: Max Length = 7
  - RegisteredOwnerCountryOfControl: Max Length = 27
  - RegisteredOwnerCountryofDomicile: Max Length = 27
  - RegisteredOwnerCountryOfRegistration: Max Length = 27
  - ShipManager: Max Length = 73
  - ShipManagerCompanyCode: Max Length = 7
  - ShipManagerCountryOfControl: Max Length = 27
  - ShipManagerCountryofDomicileName: Max Length = 27
  - ShipManagerCountryOfRegistration: Max Length = 27
  - TechnicalManager: Max Length = 30
  - TechnicalManagerCode: Max Length = 7
  - TechnicalManagerCountryOfControl: Max Length = 27
  - TechnicalManagerCountryOfDomicile: Max Length = 27
  - TechnicalManagerCountryOfRegistration: Max Length = 27
  - DOCCompany: Max Length = 30
  - DocumentofComplianceDOCCompanyCode: Max Length = 7
  - DOCCountryOfControl: Max Length = 27
  - DOCCompanyCountryofDomicile: Max Length = 27
  - DOCCountryOfRegistration: Max Length = 27
  - LastUpdateDate: Max Length = 29
  - Shipbuilder: Max Length = 30
  - ShipbuilderSubContractorShipyardYardHul: Max Length = 22
  - ShipbuilderSubContractor: Max Length = 22
  - GroupBeneficialOwnerCountryOfReg: Max Length = 27
--------------------------------------------------
File: IHSRegVessels.txt
  - EntityGUID: Max Length = 36
  - IHSRegVesselsGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 15
  - LastUpdated: Max Length = 23
  - Vessel Type: Max Length = 49
  - Gross Tonnage: Max Length = 11
  - Country of Build: Max Length = 38
  - Year of Build: Max Length = 4
  - Yard Number: Max Length = 13
  - Ship Status: Max Length = 29
  - Deadweight: Max Length = 11
  - Port of Registry: Max Length = 20
  - Source Name: Max Length = 35
  - ExName: Max Length = 48
  - FlagEffectiveDate: Max Length = 7
  - ShipStatusEffectiveDate: Max Length = 8
  - GroupBeneficialOwner: Max Length = 30
  - GroupBeneficialOwnerCompanyCode: Max Length = 7
  - GroupBeneficialOwnerCountryOfControl: Max Length = 27
  - GroupBeneficialOwnerCountryofDomicile: Max Length = 27
  - Operator: Max Length = 30
  - OperatorCompanyCode: Max Length = 7
  - OperatorCountryOfControl: Max Length = 27
  - OperatorCountryofDomicileName: Max Length = 27
  - OperatorCountryOfRegistration: Max Length = 27
  - RegisteredOwner: Max Length = 30
  - RegisteredOwnerCode: Max Length = 7
  - RegisteredOwnerCountryOfControl: Max Length = 27
  - RegisteredOwnerCountryofDomicile: Max Length = 27
  - RegisteredOwnerCountryOfRegistration: Max Length = 27
  - ShipManager: Max Length = 30
  - ShipManagerCompanyCode: Max Length = 7
  - ShipManagerCountryOfControl: Max Length = 27
  - ShipManagerCountryofDomicileName: Max Length = 27
  - ShipManagerCountryOfRegistration: Max Length = 27
  - TechnicalManager: Max Length = 30
  - TechnicalManagerCode: Max Length = 7
  - TechnicalManagerCountryOfControl: Max Length = 27
  - TechnicalManagerCountryOfDomicile: Max Length = 27
  - TechnicalManagerCountryOfRegistration: Max Length = 27
  - DOCCompany: Max Length = 30
  - DocumentofComplianceDOCCompanyCode: Max Length = 7
  - DOCCountryOfControl: Max Length = 27
  - DOCCompanyCountryofDomicile: Max Length = 27
  - DOCCountryOfRegistration: Max Length = 27
  - LastUpdateDate: Max Length = 29
  - Shipbuilder: Max Length = 37
  - ShipbuilderSubContractorShipyardYardHul: Max Length = 12
  - ShipbuilderSubContractor: Max Length = 22
  - GroupBeneficialOwnerCountryOfReg: Max Length = 27
--------------------------------------------------
File: MarijuanaRegBus.txt
  - EntityGUID: Max Length = 36
  - MarijuanaRegBusGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 17
  - LastUpdated: Max Length = 23
  - Source Name: Max Length = 37
--------------------------------------------------
File: OwnershipOrControl.txt
  - EntityGUID: Max Length = 36
  - OwnershipOrControlGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 20
  - LastUpdated: Max Length = 23
  - Source Name: Max Length = 79
  - OwnershipPercentageCalc: Max Length = 0
--------------------------------------------------
File: SWIFTBICEntity.txt
  - EntityGUID: Max Length = 36
  - SWIFTBICEntityGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 16
  - LastUpdated: Max Length = 23
  - Source Name: Max Length = 79
--------------------------------------------------
File: UAEMSB.txt
  - EntityGUID: Max Length = 36
  - UAEMSBGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 7
  - LastUpdated: Max Length = 23
  - Registration Type: Max Length = 20
  - Number of Branches: Max Length = 2
  - Source Name: Max Length = 30
  - Receive Date: Max Length = 0
  - Authorized Signature: Max Length = 0
--------------------------------------------------
File: USMSB.txt
  - EntityGUID: Max Length = 36
  - USMSBGUID: Max Length = 36
  - SubCategoryLabel: Max Length = 6
  - LastUpdated: Max Length = 23
  - Registration Type: Max Length = 20
  - Number of Branches: Max Length = 5
  - Source Name: Max Length = 29
  - Receive Date: Max Length = 10
  - Authorized Signature Date: Max Length = 10
--------------------------------------------------

                    
                    max_lengths = [0] * len(header)
                    
                    for line_bytes in f:
                        line = line_bytes.decode("utf-8", errors="ignore")
                        fields = line.strip('\r\n').split('|')
                        for i, val in enumerate(fields):
                            if i < len(max_lengths):
                                val_len = len(val.strip()) if val else 0
                                if val_len > max_lengths[i]:
                                    max_lengths[i] = val_len
                                    
                print(f"✅ COMPLETED: {filename}\n")
                for col, max_len in zip(header, max_lengths):
                    res_line = f"  - {col}: Max Length = {max_len}"
                    print(res_line)
                    out_lines.append(res_line + "\n")
                print("-" * 50)
                out_lines.append("-" * 50 + "\n")
                
            except Exception as e:
                print(f"❌ Error reading {filename}: {e}\n")
                out_lines.append(f"Error reading {filename}: {e}\n")

# Save all results to a text file
with open(output_file, "w", encoding="utf-8") as out_f:
    out_f.writelines(out_lines)

print(f"\nAll files scanned! Results saved in: {output_file}")
