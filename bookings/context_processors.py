from .models import CompanyBillingSettings


def company_branding(request):
    settings = CompanyBillingSettings.objects.only("legal_name", "logo").filter(pk=1).first()
    return {"company_branding": settings}
